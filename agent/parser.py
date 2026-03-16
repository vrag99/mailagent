import email
import email.utils
from dataclasses import dataclass
from email.message import Message
from pathlib import Path


@dataclass
class ParsedEmail:
    filepath: str
    from_addr: str
    from_email: str
    to_addr: str
    subject: str
    date: str
    message_id: str
    in_reply_to: str | None
    references: str | None
    body_plain: str
    body_truncated: str
    raw_msg: Message


def _extract_body(msg: Message) -> str:
    plain_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" in disp:
                continue
            if ct == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    plain_parts.append(payload.decode(charset, errors="replace"))
            elif ct == "text/html":
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    html_parts.append(payload.decode(charset, errors="replace"))
    else:
        ct = msg.get_content_type()
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            if ct == "text/plain":
                plain_parts.append(payload.decode(charset, errors="replace"))
            elif ct == "text/html":
                html_parts.append(payload.decode(charset, errors="replace"))

    if plain_parts:
        return "\n".join(plain_parts)

    if html_parts:
        from bs4 import BeautifulSoup
        combined = "\n".join(html_parts)
        return BeautifulSoup(combined, "html.parser").get_text(separator="\n")

    return ""


def parse(filepath: str) -> ParsedEmail:
    raw = Path(filepath).read_bytes()
    msg = email.message_from_bytes(raw)

    from_addr = msg.get("From", "")
    _, from_email = email.utils.parseaddr(from_addr)

    body = _extract_body(msg)

    return ParsedEmail(
        filepath=filepath,
        from_addr=from_addr,
        from_email=from_email.lower(),
        to_addr=msg.get("To", ""),
        subject=msg.get("Subject", ""),
        date=msg.get("Date", ""),
        message_id=msg.get("Message-ID", ""),
        in_reply_to=msg.get("In-Reply-To"),
        references=msg.get("References"),
        body_plain=body,
        body_truncated=body[:2000],
        raw_msg=msg,
    )
