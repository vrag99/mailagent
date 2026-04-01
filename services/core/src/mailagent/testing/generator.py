"""LLM-based email generation for test cases."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..providers import BaseProvider

logger = logging.getLogger(__name__)


@dataclass
class GeneratedEmail:
    from_addr: str
    subject: str
    body: str


_EMAIL_RE = re.compile(
    r"FROM:\s*(.+?)\s*\n"
    r"SUBJECT:\s*(.+?)\s*\n"
    r"BODY:\s*\n(.*)",
    re.DOTALL,
)

_SYSTEM_PROMPT = (
    "You generate realistic test emails for testing email classification systems.\n"
    "Generate a complete email with From, Subject, and Body fields.\n"
    "The email should be realistic — natural language, plausible sender, appropriate formatting for the type.\n"
    "Respond ONLY in this exact format, nothing else:\n\n"
    "FROM: sender@example.com\n"
    "SUBJECT: The email subject line\n"
    "BODY:\n"
    "The full email body text here.\n"
    "Can be multiple lines."
)


def generate_email(
    provider: BaseProvider,
    description: str,
    from_override: str | None = None,
) -> GeneratedEmail:
    user_prompt = f"Generate an email matching this description:\n{description}"
    if from_override:
        user_prompt += f"\n\nThe sender should be: {from_override}"
    user_prompt += "\n\nMake it realistic and varied. Do not include placeholder text like [brackets] or <angle brackets>."

    raw = provider.generate(system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt)
    return _parse_single(raw, from_override)


def generate_batch(
    provider: BaseProvider,
    description: str,
    count: int,
) -> list[GeneratedEmail]:
    user_prompt = (
        f"Generate {count} DIFFERENT emails matching this description:\n"
        f"{description}\n\n"
        "Each email should have a different sender, writing style, and specific details.\n"
        'Separate each email with a line containing only "---".\n\n'
    )
    for i in range(1, count + 1):
        user_prompt += f"EMAIL {i}:\nFROM: ...\nSUBJECT: ...\nBODY:\n...\n"
        if i < count:
            user_prompt += "---\n"

    user_prompt += "\nMake them realistic and varied. Do not include placeholder text like [brackets] or <angle brackets>."

    raw = provider.generate(system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt)
    emails: list[GeneratedEmail] = []

    chunks = re.split(r"\n-{3,}\n", raw)
    for i, chunk in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Strip leading "EMAIL N:" prefix if present
        chunk = re.sub(r"^EMAIL\s+\d+:\s*\n?", "", chunk, flags=re.IGNORECASE)
        try:
            emails.append(_parse_single(chunk, None))
        except ValueError:
            logger.warning("Failed to parse email %d in batch; skipping", i + 1)

    return emails


def _parse_single(raw: str, from_override: str | None) -> GeneratedEmail:
    match = _EMAIL_RE.search(raw)
    if not match:
        raise ValueError(f"Could not parse generated email from response:\n{raw[:200]}")

    from_addr = from_override or match.group(1).strip()
    subject = match.group(2).strip()
    body = match.group(3).strip()

    return GeneratedEmail(from_addr=from_addr, subject=subject, body=body)
