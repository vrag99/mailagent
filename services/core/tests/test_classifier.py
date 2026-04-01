from mailagent.core.classifier import _classify_keywords, classify
from mailagent.config import KeywordMatch, Workflow, WorkflowAction, WorkflowMatch
from mailagent.core.parser import parse
from mailagent.providers import ProviderError
from mailagent.core.state import ThreadContext


class FakeProvider:
    def __init__(self, value: str = "", should_raise: bool = False):
        self.value = value
        self.should_raise = should_raise

    def classify(self, _system: str, _user: str) -> str:
        if self.should_raise:
            raise ProviderError("boom")
        return self.value


def _workflows():
    return [
        Workflow(
            name="meeting-request",
            match=WorkflowMatch(
                intent="requesting a meeting",
                keywords=KeywordMatch(any=["meeting", "call"]),
            ),
            action=WorkflowAction(type="reply", prompt="reply"),
        ),
        Workflow(
            name="newsletter",
            match=WorkflowMatch(
                intent="newsletter",
                keywords=KeywordMatch(any=["digest"]),
            ),
            action=WorkflowAction(type="ignore"),
        ),
        Workflow(
            name="fallback",
            match=WorkflowMatch(intent="default"),
            action=WorkflowAction(type="ignore"),
        ),
    ]


def test_llm_path_returns_workflow(plain_text_eml):
    parsed = parse(plain_text_eml)
    provider = FakeProvider('{"workflow": "meeting-request"}')

    result = classify(parsed, _workflows(), provider, "You are assistant")
    assert result.workflow_name == "meeting-request"
    assert result.method == "llm"


def test_garbled_llm_falls_to_keywords(plain_text_eml):
    parsed = parse(plain_text_eml)
    provider = FakeProvider("nonsense")

    result = classify(parsed, _workflows(), provider, "You are assistant")
    assert result.workflow_name == "meeting-request"
    assert result.method == "keyword"


def test_llm_exception_falls_to_keywords(mailing_list_eml):
    parsed = parse(mailing_list_eml)
    provider = FakeProvider(should_raise=True)

    result = classify(parsed, _workflows(), provider, "You are assistant")
    assert result.workflow_name == "newsletter"
    assert result.method == "keyword"


def test_keywords_any_and_all_logic():
    workflows = [
        Workflow(
            name="meeting-request",
            match=WorkflowMatch(
                intent="requesting a meeting",
                keywords=KeywordMatch(any=["call"], all=["schedule"]),
            ),
            action=WorkflowAction(type="reply", prompt="reply"),
        ),
        Workflow(
            name="fallback",
            match=WorkflowMatch(intent="default"),
            action=WorkflowAction(type="ignore"),
        ),
    ]

    class Dummy:
        subject = "Please schedule"
        body_plain = "Can we have a call tomorrow"

    assert _classify_keywords(Dummy(), workflows) == "meeting-request"

    Dummy.subject = "Please schedule"
    Dummy.body_plain = "No keyword"
    assert _classify_keywords(Dummy(), workflows) is None


def test_full_fallback_chain_to_fallback(non_utf8_eml):
    parsed = parse(non_utf8_eml)
    provider = FakeProvider(should_raise=True)

    workflows = [
        Workflow(
            name="only-llm",
            match=WorkflowMatch(intent="some intent"),
            action=WorkflowAction(type="ignore"),
        ),
        Workflow(
            name="fallback",
            match=WorkflowMatch(intent="default"),
            action=WorkflowAction(type="ignore"),
        ),
    ]

    result = classify(parsed, workflows, provider, "You are assistant")
    assert result.workflow_name == "fallback"
    assert result.method == "keyword"


def test_classify_includes_thread_annotation(plain_text_eml):
    parsed = parse(plain_text_eml)
    captured_user_prompt = {}

    class CapturingProvider:
        def classify(self, system: str, user: str) -> str:
            captured_user_prompt["text"] = user
            return '{"workflow": "meeting-request"}'

    thread_ctx = ThreadContext(is_reply=True, is_reply_to_own=True, depth=2)
    classify(parsed, _workflows(), CapturingProvider(), "You are assistant", thread_ctx=thread_ctx)

    assert "[Thread context:" in captured_user_prompt["text"]
    assert "Thread depth: 2" in captured_user_prompt["text"]


def test_classify_no_annotation_when_not_own_reply(plain_text_eml):
    parsed = parse(plain_text_eml)
    captured_user_prompt = {}

    class CapturingProvider:
        def classify(self, system: str, user: str) -> str:
            captured_user_prompt["text"] = user
            return '{"workflow": "meeting-request"}'

    thread_ctx = ThreadContext(is_reply=True, is_reply_to_own=False, depth=0)
    classify(parsed, _workflows(), CapturingProvider(), "You are assistant", thread_ctx=thread_ctx)

    assert "[Thread context:" not in captured_user_prompt["text"]
