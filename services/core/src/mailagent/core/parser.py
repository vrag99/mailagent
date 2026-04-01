import email
import email.utils
from dataclasses import dataclass
from email.message import Message
from pathlib import Path

from bs4 import BeautifulSoup


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


def parse(filepath: str | Path, truncate_at: int = 2000) -> ParsedEmail:
    path = Path(filepath)
    raw = path.read_bytes()
    msg = email.message_from_bytes(raw)

    from_addr = msg.get("From", "")
    _, from_email = email.utils.parseaddr(from_addr)
    body = _extract_body(msg)

    return ParsedEmail(
        filepath=str(path),
        from_addr=from_addr,
        from_email=from_email.lower(),
        to_addr=msg.get("To", ""),
        subject=msg.get("Subject", ""),
        date=msg.get("Date", ""),
        message_id=msg.get("Message-ID", ""),
        in_reply_to=msg.get("In-Reply-To"),
        references=msg.get("References"),
        body_plain=body,
        body_truncated=body[:truncate_at],
        raw_msg=msg,
    )


def _extract_body(msg: Message) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            _append_part(part, plain_parts, html_parts)
    else:
        _append_part(msg, plain_parts, html_parts)

    if plain_parts:
        return "\n".join(plain_parts).strip()

    if html_parts:
        html = "\n".join(html_parts)
        return BeautifulSoup(html, "html.parser").get_text(separator="\n").strip()

    return ""


def _append_part(part: Message, plain_parts: list[str], html_parts: list[str]) -> None:
    content_type = part.get_content_type()
    disposition = str(part.get("Content-Disposition", ""))

    if "attachment" in disposition.lower():
        return

    if content_type not in {"text/plain", "text/html"}:
        return

    payload = part.get_payload(decode=True)
    if not payload:
        return

    charset = part.get_content_charset() or "utf-8"
    try:
        text = payload.decode(charset, errors="replace")
    except LookupError:
        text = payload.decode("utf-8", errors="replace")

    if content_type == "text/plain":
        plain_parts.append(text)
    else:
        html_parts.append(text)
