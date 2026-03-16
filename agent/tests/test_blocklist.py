import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import workflows
from parser import parse

FIXTURES = Path(__file__).parent / "fixtures"


def _make_config(**overrides):
    defaults = dict(
        inbox="hi@garv.me",
        blocklist_from_patterns=["noreply@", "no-reply@", "mailer-daemon@", "list-", "notifications@", "alert@"],
        blocklist_headers=["List-Unsubscribe", "Precedence: bulk", "Precedence: list", "X-Auto-Response-Suppress"],
        workflows=[
            {
                "name": "meeting-request",
                "match": {"intent": "requesting a meeting"},
                "action": {"type": "reply", "prompt": "You are Garv."},
            }
        ],
    )
    defaults.update(overrides)
    return workflows.Config(**defaults)


def test_noreply_is_blocked():
    config = _make_config()
    em = parse(str(FIXTURES / "noreply.eml"))
    with patch("llm.generate_reply") as mock_reply:
        workflows.execute("meeting-request", em, config)
        mock_reply.assert_not_called()


def test_list_unsubscribe_header_blocked():
    config = _make_config()
    em = parse(str(FIXTURES / "noreply.eml"))  # has List-Unsubscribe
    with patch("llm.generate_reply") as mock_reply:
        workflows.execute("meeting-request", em, config)
        mock_reply.assert_not_called()


def test_self_address_blocked(monkeypatch):
    monkeypatch.setenv("MAIL_USER", "hi")
    monkeypatch.setenv("MAIL_DOMAIN", "garv.me")
    config = _make_config()
    em = parse(str(FIXTURES / "plain.eml"))
    # Patch from_email to be the own address
    em.from_email = "hi@garv.me"
    with patch("llm.generate_reply") as mock_reply:
        workflows.execute("meeting-request", em, config)
        mock_reply.assert_not_called()


def test_normal_sender_not_blocked():
    config = _make_config()
    em = parse(str(FIXTURES / "plain.eml"))
    with patch("llm.generate_reply", return_value="Hi there!"), \
         patch("mailer.send_reply", return_value=MagicMock()), \
         patch("mailer.save_to_sent"), \
         patch("mailer.flag_original_replied"):
        workflows.execute("meeting-request", em, config)
