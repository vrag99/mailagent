import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import Message
import email.utils

from imapclient import IMAPClient

from parser import ParsedEmail

logger = logging.getLogger(__name__)

SMTP_PORT = 587
IMAP_PORT = 143

SENT_FOLDER_CANDIDATES = ["Sent", "Sent Messages"]


def _cfg() -> tuple[str, str, str, str]:
    """Return (host, user, domain, password) read fresh from env each call."""
    return (
        os.environ.get("MAIL_HOST", "mailserver"),
        os.environ.get("MAIL_USER", ""),
        os.environ.get("MAIL_DOMAIN", ""),
        os.environ.get("MAIL_PASSWORD", ""),
    )


def _smtp_address() -> str:
    _, user, domain, _ = _cfg()
    return f"{user}@{domain}"


def send_reply(original: ParsedEmail, body_text: str) -> Message:
    host, _, domain, password = _cfg()

    subject = original.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    references = original.references or ""
    if original.message_id:
        references = f"{references} {original.message_id}".strip()

    reply = MIMEMultipart()
    reply["From"] = _smtp_address()
    reply["To"] = original.from_addr
    reply["Subject"] = subject
    reply["Date"] = email.utils.formatdate(localtime=True)
    reply["Message-ID"] = email.utils.make_msgid(domain=domain)
    reply["In-Reply-To"] = original.message_id
    reply["References"] = references
    reply.attach(MIMEText(body_text, "plain", "utf-8"))

    with smtplib.SMTP(host, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(_smtp_address(), password)
        smtp.send_message(reply)

    logger.debug("Sent reply to %s", original.from_addr)
    return reply


def _get_or_create_sent(client: IMAPClient) -> str:
    folders = [f[2] for f in client.list_folders()]
    for candidate in SENT_FOLDER_CANDIDATES:
        if candidate in folders:
            return candidate
    client.create_folder("Sent")
    return "Sent"


def save_to_sent(reply_msg: Message) -> None:
    host, _, _, password = _cfg()
    with IMAPClient(host, port=IMAP_PORT, ssl=False) as client:
        client.starttls()
        client.login(_smtp_address(), password)
        sent_folder = _get_or_create_sent(client)
        client.append(sent_folder, reply_msg.as_bytes(), flags=[b"\\Seen"])
    logger.debug("Saved reply to %s folder", sent_folder)


def flag_original_replied(original: ParsedEmail) -> None:
    if not original.message_id:
        return
    host, _, _, password = _cfg()
    with IMAPClient(host, port=IMAP_PORT, ssl=False) as client:
        client.starttls()
        client.login(_smtp_address(), password)
        client.select_folder("INBOX")
        uids = client.search(["HEADER", "Message-ID", original.message_id])
        if uids:
            client.add_flags(uids, [b"\\Answered"])
            logger.debug("Flagged original message as \\Answered")
