from mailagent.core.parser import parse


def test_plain_text(plain_text_eml):
    parsed = parse(plain_text_eml)
    assert parsed.from_email == "alice@external.example"
    assert parsed.from_addr == "Alice <alice@external.example>"
    assert parsed.subject == "Let's catch up!"
    assert parsed.message_id == "<abc123@external.example>"
    assert "Would love to catch up" in parsed.body_plain
    assert parsed.in_reply_to is None
    assert parsed.references is None


def test_html_only_falls_back(html_only_eml):
    parsed = parse(html_only_eml)
    assert "Big Sale" in parsed.body_plain
    assert "<html>" not in parsed.body_plain


def test_multipart_prefers_plain(multipart_eml):
    parsed = parse(multipart_eml)
    assert "approval" in parsed.body_plain
    assert "<b>" not in parsed.body_plain


def test_non_utf8_body_parses(non_utf8_eml):
    parsed = parse(non_utf8_eml)
    assert "Olá" in parsed.body_plain


def test_body_truncated_limit(plain_text_eml):
    parsed = parse(plain_text_eml, truncate_at=10)
    assert len(parsed.body_truncated) <= 10
