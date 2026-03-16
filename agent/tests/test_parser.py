import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import parse

FIXTURES = Path(__file__).parent / "fixtures"


def test_plain_text():
    em = parse(str(FIXTURES / "plain.eml"))
    assert em.from_email == "alice@example.com"
    assert em.from_addr == "Alice <alice@example.com>"
    assert em.subject == "Let's catch up!"
    assert em.message_id == "<abc123@example.com>"
    assert "Would love to catch up" in em.body_plain
    assert em.in_reply_to is None


def test_html_only_falls_back():
    em = parse(str(FIXTURES / "html_only.eml"))
    assert "Big Sale" in em.body_plain
    assert "<html>" not in em.body_plain


def test_multipart_prefers_plain():
    em = parse(str(FIXTURES / "multipart.eml"))
    assert "approval" in em.body_plain
    assert "<b>" not in em.body_plain


def test_body_truncated():
    em = parse(str(FIXTURES / "plain.eml"))
    assert len(em.body_truncated) <= 2000


def test_missing_headers():
    em = parse(str(FIXTURES / "plain.eml"))
    assert em.in_reply_to is None
    assert em.references is None
