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
) -> Message:
    local, domain = inbox_address.split("@", 1)

    subject = original.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    references = original.references or ""
    if original.message_id:
        references = f"{references} {original.message_id}".strip()

    reply = MIMEMultipart()
    reply["From"] = inbox_address
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


def _get_or_create_sent(client: IMAPClient) -> str:
    folders = [f[2] for f in client.list_folders()]
    for candidate in SENT_FOLDER_CANDIDATES:
        if candidate in folders:
            return candidate
    client.create_folder("Sent")
    return "Sent"
