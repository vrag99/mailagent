import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import classifier
from parser import parse

WORKFLOWS = [
    {"name": "meeting-request", "match": {"intent": "requesting a meeting, call, or video chat"}},
    {"name": "cold-outreach", "match": {"intent": "cold outreach, sales pitch, recruitment spam, marketing"}},
    {"name": "action-required", "match": {"intent": "requires personal decision, approval, or action"}},
    {"name": "fallback", "match": {"intent": "default"}},
]


def test_exact_match(plain_eml):
    with patch("llm.classify", return_value="meeting-request"):
        assert classifier.classify(parse(str(plain_eml)), WORKFLOWS) == "meeting-request"


def test_case_insensitive_match(plain_eml):
    with patch("llm.classify", return_value="Meeting-Request"):
        assert classifier.classify(parse(str(plain_eml)), WORKFLOWS) == "meeting-request"


def test_unexpected_response_falls_back(plain_eml):
    with patch("llm.classify", return_value="UNKNOWN_GARBAGE"):
        assert classifier.classify(parse(str(plain_eml)), WORKFLOWS) == "fallback"


def test_empty_response_falls_back(plain_eml):
    with patch("llm.classify", return_value="  "):
        assert classifier.classify(parse(str(plain_eml)), WORKFLOWS) == "fallback"


def test_llm_exception_falls_back(plain_eml):
    with patch("llm.classify", side_effect=Exception("API down")):
        assert classifier.classify(parse(str(plain_eml)), WORKFLOWS) == "fallback"
