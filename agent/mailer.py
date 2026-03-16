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

MAIL_HOST = os.environ.get("MAIL_HOST", "mailserver")
MAIL_USER = os.environ.get("MAIL_USER", "hi")
MAIL_DOMAIN = os.environ.get("MAIL_DOMAIN", "garv.me")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")

SMTP_PORT = 587
IMAP_PORT = 143

SENT_FOLDER_CANDIDATES = ["Sent", "Sent Messages"]


def _smtp_address() -> str:
    return f"{MAIL_USER}@{MAIL_DOMAIN}"


def send_reply(original: ParsedEmail, body_text: str) -> Message:
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
    reply["Message-ID"] = email.utils.make_msgid(domain=MAIL_DOMAIN)
    reply["In-Reply-To"] = original.message_id
    reply["References"] = references
    reply.attach(MIMEText(body_text, "plain", "utf-8"))

    with smtplib.SMTP(MAIL_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(_smtp_address(), MAIL_PASSWORD)
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
    with IMAPClient(MAIL_HOST, port=IMAP_PORT, ssl=False) as client:
        client.starttls()
        client.login(_smtp_address(), MAIL_PASSWORD)
        sent_folder = _get_or_create_sent(client)
        client.append(sent_folder, reply_msg.as_bytes(), flags=[b"\\Seen"])
    logger.debug("Saved reply to %s folder", sent_folder)


def flag_original_replied(original: ParsedEmail) -> None:
    if not original.message_id:
        return
    with IMAPClient(MAIL_HOST, port=IMAP_PORT, ssl=False) as client:
        client.starttls()
        client.login(_smtp_address(), MAIL_PASSWORD)
        client.select_folder("INBOX")
        uids = client.search(["HEADER", "Message-ID", original.message_id])
        if uids:
            client.add_flags(uids, [b"\\Answered"])
            logger.debug("Flagged original message as \\Answered")
