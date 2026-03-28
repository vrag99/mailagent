import email.utils
import logging
import smtplib
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from imapclient import IMAPClient

from .parser import ParsedEmail

logger = logging.getLogger(__name__)

SMTP_PORT = 587
IMAP_PORT = 143
SENT_FOLDER_CANDIDATES = ["Sent", "Sent Messages"]


def send_reply(
    original: ParsedEmail,
    body_text: str,
    mail_host: str,
    inbox_address: str,
    password: str,
    inbox_name: str | None = None,
) -> Message:
    local, domain = inbox_address.split("@", 1)

    subject = original.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    references = original.references or ""
    if original.message_id:
        references = f"{references} {original.message_id}".strip()

    from_header = f"{inbox_name} <{inbox_address}>" if inbox_name else inbox_address

    reply = MIMEMultipart()
    reply["From"] = from_header
    reply["To"] = original.from_addr
    reply["Subject"] = subject
    reply["Date"] = email.utils.formatdate(localtime=True)
    reply["Message-ID"] = email.utils.make_msgid(domain=domain)
    reply["In-Reply-To"] = original.message_id
    reply["References"] = references
    reply.attach(MIMEText(body_text, "plain", "utf-8"))

    with smtplib.SMTP(mail_host, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(inbox_address, password)
        smtp.send_message(reply)

    logger.debug("Sent reply to %s from %s", original.from_addr, inbox_address)
    return reply


def send_email(
    mail_host: str,
    inbox_address: str,
    password: str,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    content_type: str = "plain",
    inbox_name: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> Message:
    """Compose and send a fresh email (not necessarily a reply)."""
    _, domain = inbox_address.split("@", 1)

    from_header = f"{inbox_name} <{inbox_address}>" if inbox_name else inbox_address

    msg = MIMEMultipart()
    msg["From"] = from_header
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=domain)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.attach(MIMEText(body, content_type, "utf-8"))

    all_recipients = list(to) + (cc or []) + (bcc or [])

    with smtplib.SMTP(mail_host, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(inbox_address, password)
        smtp.send_message(msg, to_addrs=all_recipients)

    logger.debug("Sent email to %s from %s", to, inbox_address)
    return msg


def save_to_sent(
    msg: Message,
    mail_host: str,
    inbox_address: str,
    password: str,
) -> None:
    """Save a message to the Sent folder via IMAP."""
    with IMAPClient(mail_host, port=IMAP_PORT, ssl=False) as client:
        client.starttls()
        client.login(inbox_address, password)
        sent_folder = _get_or_create_sent(client)
        client.append(sent_folder, msg.as_bytes(), flags=[b"\\Seen"])
        logger.debug("Saved message to %s folder", sent_folder)


def save_and_flag_replied(
    reply_msg: Message,
    original: ParsedEmail,
    mail_host: str,
    inbox_address: str,
    password: str,
) -> None:
    with IMAPClient(mail_host, port=IMAP_PORT, ssl=False) as client:
        client.starttls()
        client.login(inbox_address, password)
        sent_folder = _get_or_create_sent(client)
        client.append(sent_folder, reply_msg.as_bytes(), flags=[b"\\Seen"])
        logger.debug("Saved reply to %s folder", sent_folder)
        if original.message_id:
            client.select_folder("INBOX")
            uids = client.search(["HEADER", "Message-ID", original.message_id])
            if uids:
                client.add_flags(uids, [b"\\Answered"])
                logger.debug("Flagged original as \\Answered")


def fetch_thread_messages(
    references: str | None,
    mail_host: str,
    inbox_address: str,
    password: str,
    max_messages: int = 5,
) -> list:
    """Retrieve prior messages in a thread via IMAP using the References header."""
    from .state import ThreadMessage

    if not references:
        return []

    message_ids = references.strip().split()
    if not message_ids:
        return []

    results: list[ThreadMessage] = []

    try:
        with IMAPClient(mail_host, port=IMAP_PORT, ssl=False) as client:
            client.starttls()
            client.login(inbox_address, password)

            folders_to_search = ["INBOX"]
            all_folders = [f[2] for f in client.list_folders()]
            for candidate in SENT_FOLDER_CANDIDATES:
                if candidate in all_folders:
                    folders_to_search.append(candidate)
                    break

            seen_ids: set[str] = set()

            for mid in message_ids[-max_messages:]:
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)

                for folder in folders_to_search:
                    client.select_folder(folder, readonly=True)
                    uids = client.search(["HEADER", "Message-ID", mid])
                    if not uids:
                        continue

                    fetched = client.fetch(uids[:1], ["BODY.PEEK[]"])
                    for uid, data in fetched.items():
                        raw_bytes = data.get(b"BODY[]", b"")
                        if not raw_bytes:
                            continue
                        msg = email.message_from_bytes(raw_bytes)
                        from_addr = msg.get("From", "")
                        date = msg.get("Date", "")
                        body = _extract_plain_body(msg)[:500]
                        results.append(
                            ThreadMessage(
                                message_id=mid,
                                from_addr=from_addr,
                                date=date,
                                body_snippet=body,
                            )
                        )
                    break  # found in this folder, skip other folders

                if len(results) >= max_messages:
                    break
    except Exception as exc:
        logger.warning("Failed to fetch thread messages: %s", exc)

    return results


def _extract_plain_body(msg: Message) -> str:
    """Extract plain text body from a message (simple helper for thread fetching)."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        return payload.decode(charset, errors="replace")
                    except LookupError:
                        return payload.decode("utf-8", errors="replace")
        return ""
    if msg.get_content_type() == "text/plain":
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset, errors="replace")
            except LookupError:
                return payload.decode("utf-8", errors="replace")
    return ""


def _get_or_create_sent(client: IMAPClient) -> str:
    folders = [f[2] for f in client.list_folders()]
    for candidate in SENT_FOLDER_CANDIDATES:
        if candidate in folders:
            return candidate
    client.create_folder("Sent")
    return "Sent"
