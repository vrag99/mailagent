import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import classifier
from parser import parse

FIXTURES = Path(__file__).parent / "fixtures"

WORKFLOWS = [
    {"name": "meeting-request", "match": {"intent": "requesting a meeting, call, or video chat"}},
    {"name": "cold-outreach", "match": {"intent": "cold outreach, sales pitch, recruitment spam, marketing"}},
    {"name": "action-required", "match": {"intent": "requires personal decision, approval, or action"}},
    {"name": "fallback", "match": {"intent": "default"}},
]


def _email():
    return parse(str(FIXTURES / "plain.eml"))


def test_exact_match():
    with patch("llm.classify", return_value="meeting-request"):
        result = classifier.classify(_email(), WORKFLOWS)
    assert result == "meeting-request"


def test_case_insensitive_match():
    with patch("llm.classify", return_value="Meeting-Request"):
        result = classifier.classify(_email(), WORKFLOWS)
    assert result == "meeting-request"


def test_unexpected_response_falls_back():
    with patch("llm.classify", return_value="UNKNOWN_GARBAGE"):
        result = classifier.classify(_email(), WORKFLOWS)
    assert result == "fallback"


def test_empty_response_falls_back():
    with patch("llm.classify", return_value="  "):
        result = classifier.classify(_email(), WORKFLOWS)
    assert result == "fallback"


def test_llm_exception_falls_back():
    with patch("llm.classify", side_effect=Exception("API down")):
        result = classifier.classify(_email(), WORKFLOWS)
    assert result == "fallback"
