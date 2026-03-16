import os
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mail_env(monkeypatch):
    """Ensure mail env vars are set for every test, falling back to safe defaults."""
    monkeypatch.setenv("MAIL_USER", os.environ.get("MAIL_USER", "you"))
    monkeypatch.setenv("MAIL_DOMAIN", os.environ.get("MAIL_DOMAIN", "example.com"))
    monkeypatch.setenv("MAIL_PASSWORD", os.environ.get("MAIL_PASSWORD", "testpassword"))
    monkeypatch.setenv("MAIL_HOST", os.environ.get("MAIL_HOST", "mailserver"))
    monkeypatch.setenv("OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", "test-key"))


# ---------------------------------------------------------------------------
# Email fixture factory
# ---------------------------------------------------------------------------

def _inbox() -> str:
    return f"{os.environ.get('MAIL_USER', 'you')}@{os.environ.get('MAIL_DOMAIN', 'example.com')}"


def _write_eml(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content).lstrip())
    return p


@pytest.fixture()
def plain_eml(tmp_path):
    """Plain-text email from an external sender."""
    return _write_eml(tmp_path, "plain.eml", f"""\
        From: Alice <alice@external.example>
        To: {_inbox()}
        Subject: Let's catch up!
        Date: Mon, 10 Mar 2025 10:00:00 +0000
        Message-ID: <abc123@external.example>
        Content-Type: text/plain; charset=utf-8

        Hi,

        Would love to catch up sometime. Are you free for a quick call this week?

        Best,
        Alice
    """)


@pytest.fixture()
def html_eml(tmp_path):
    """HTML-only email (no text/plain part)."""
    return _write_eml(tmp_path, "html_only.eml", f"""\
        From: Marketing <marketing@company.example>
        To: {_inbox()}
        Subject: Special offer just for you!
        Date: Mon, 10 Mar 2025 10:00:00 +0000
        Message-ID: <promo456@company.example>
        Content-Type: text/html; charset=utf-8

        <html><body><h1>Big Sale!</h1><p>Get 50% off everything today.</p></body></html>
    """)


@pytest.fixture()
def multipart_eml(tmp_path):
    """Multipart/alternative email with both text and HTML parts."""
    return _write_eml(tmp_path, "multipart.eml", f"""\
        From: Bob <bob@external.example>
        To: {_inbox()}
        Subject: Project approval needed
        Date: Mon, 10 Mar 2025 10:00:00 +0000
        Message-ID: <multi789@external.example>
        MIME-Version: 1.0
        Content-Type: multipart/alternative; boundary="boundary42"

        --boundary42
        Content-Type: text/plain; charset=utf-8

        Hi,

        I need your approval on the Q2 budget proposal. Please review and get back to me.

        Thanks,
        Bob

        --boundary42
        Content-Type: text/html; charset=utf-8

        <html><body><p>Hi,</p><p>I need your <b>approval</b> on the Q2 budget proposal.</p></body></html>

        --boundary42--
    """)


@pytest.fixture()
def noreply_eml(tmp_path):
    """Automated/list email that should always be blocked."""
    return _write_eml(tmp_path, "noreply.eml", f"""\
        From: noreply@service.example
        To: {_inbox()}
        Subject: Your weekly digest
        Date: Mon, 10 Mar 2025 10:00:00 +0000
        Message-ID: <digest@service.example>
        List-Unsubscribe: <mailto:unsub@service.example>
        Content-Type: text/plain; charset=utf-8

        Here is your weekly digest...
    """)


@pytest.fixture()
def self_eml(tmp_path):
    """Email that appears to come from the inbox owner's own address."""
    own = _inbox()
    return _write_eml(tmp_path, "self.eml", f"""\
        From: {own}
        To: {own}
        Subject: Test self-send
        Date: Mon, 10 Mar 2025 10:00:00 +0000
        Message-ID: <self001@{os.environ.get('MAIL_DOMAIN', 'example.com')}>
        Content-Type: text/plain; charset=utf-8

        This email came from the inbox owner's own address.
    """)
