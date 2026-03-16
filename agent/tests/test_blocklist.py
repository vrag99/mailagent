import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import workflows
from parser import parse


def _make_config(**overrides):
    defaults = dict(
        inbox=f"{os.environ.get('MAIL_USER', 'you')}@{os.environ.get('MAIL_DOMAIN', 'example.com')}",
        blocklist_from_patterns=["noreply@", "no-reply@", "mailer-daemon@", "list-", "notifications@", "alert@"],
        blocklist_headers=["List-Unsubscribe", "Precedence: bulk", "Precedence: list", "X-Auto-Response-Suppress"],
        workflows=[
            {
                "name": "meeting-request",
                "match": {"intent": "requesting a meeting"},
                "action": {"type": "reply", "prompt": "You are the inbox owner."},
            }
        ],
    )
    defaults.update(overrides)
    return workflows.Config(**defaults)


def test_noreply_sender_blocked(noreply_eml):
    em = parse(str(noreply_eml))
    with patch("llm.generate_reply") as mock_reply:
        workflows.execute("meeting-request", em, _make_config())
        mock_reply.assert_not_called()


def test_list_unsubscribe_header_blocked(noreply_eml):
    em = parse(str(noreply_eml))  # has List-Unsubscribe header
    with patch("llm.generate_reply") as mock_reply:
        workflows.execute("meeting-request", em, _make_config())
        mock_reply.assert_not_called()


def test_self_address_blocked(self_eml):
    """Email from the inbox owner's own address must never trigger a reply."""
    em = parse(str(self_eml))
    with patch("llm.generate_reply") as mock_reply:
        workflows.execute("meeting-request", em, _make_config())
        mock_reply.assert_not_called()


def test_normal_sender_not_blocked(plain_eml):
    em = parse(str(plain_eml))
    with patch("llm.generate_reply", return_value="Hi there!"), \
         patch("mailer.send_reply", return_value=MagicMock()), \
         patch("mailer.save_to_sent"), \
         patch("mailer.flag_original_replied"):
        workflows.execute("meeting-request", em, _make_config())
