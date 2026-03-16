import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import parse


def test_plain_text(plain_eml):
    em = parse(str(plain_eml))
    assert em.from_email == "alice@external.example"
    assert em.from_addr == "Alice <alice@external.example>"
    assert em.subject == "Let's catch up!"
    assert em.message_id == "<abc123@external.example>"
    assert "Would love to catch up" in em.body_plain
    assert em.in_reply_to is None
    assert em.references is None


def test_to_address_matches_inbox(plain_eml):
    import os
    em = parse(str(plain_eml))
    expected = f"{os.environ['MAIL_USER']}@{os.environ['MAIL_DOMAIN']}"
    assert em.to_addr == expected


def test_html_only_falls_back(html_eml):
    em = parse(str(html_eml))
    assert "Big Sale" in em.body_plain
    assert "<html>" not in em.body_plain


def test_multipart_prefers_plain(multipart_eml):
    em = parse(str(multipart_eml))
    assert "approval" in em.body_plain
    assert "<b>" not in em.body_plain


def test_body_truncated(plain_eml):
    em = parse(str(plain_eml))
    assert len(em.body_truncated) <= 2000


def test_missing_headers(plain_eml):
    em = parse(str(plain_eml))
    assert em.in_reply_to is None
    assert em.references is None
