from unittest.mock import patch

from mailagent.config import (
    Blocklist,
    Config,
    Defaults,
    InboxConfig,
    Settings,
    Workflow,
    WorkflowAction,
    WorkflowMatch,
)
from mailagent.core.parser import parse
from mailagent.core.state import ThreadContext, ThreadMessage
from mailagent.core.workflows import execute


class FakeProvider:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        _ = (system_prompt, user_prompt)
        return "Thanks for reaching out."


def _config() -> tuple[Config, InboxConfig]:
    wf_reply = Workflow(
        name="meeting-request",
        match=WorkflowMatch(intent="request meeting"),
        action=WorkflowAction(type="reply", prompt="Keep it short"),
    )
    wf_notify = Workflow(
        name="urgent",
        match=WorkflowMatch(intent="urgent"),
        action=WorkflowAction(
            type="notify",
            webhook="https://example.com/hook",
            also_reply=True,
            prompt="Ack",
        ),
    )
    wf_webhook = Workflow(
        name="invoice",
        match=WorkflowMatch(intent="invoice"),
        action=WorkflowAction(
            type="webhook",
            url="https://example.com/invoice",
            payload={"subject": "{{subject}}", "from": "{{from}}"},
        ),
    )
    wf_fallback = Workflow(
        name="fallback",
        match=WorkflowMatch(intent="default"),
        action=WorkflowAction(type="ignore"),
    )

    inbox = InboxConfig(
        address="you@example.com",
        credentials={"password": "secret"},
        workflows=[wf_reply, wf_notify, wf_webhook, wf_fallback],
        classify_provider="fast",
        reply_provider="fast",
        system_prompt="You are helpful",
        blocklist=Blocklist(
            from_patterns=["noreply@"],
            headers=["List-Unsubscribe"],
        ),
    )
    config = Config(
        providers={},
        defaults=Defaults(classify_provider="fast", reply_provider="fast"),
        inboxes=[inbox],
        settings=Settings(),
    )
    return config, inbox


def test_reply_blocked_for_blocklist(mailing_list_eml):
    config, inbox = _config()
    parsed = parse(mailing_list_eml)

    out = execute(
        workflow_name="meeting-request",
        parsed_email=parsed,
        inbox=inbox,
        config=config,
        reply_provider=FakeProvider(),
        dry_run=False,
    )

    assert out["ok"] is True
    assert out["blocked"] is True


def test_webhook_action_dry_run(plain_text_eml):
    config, inbox = _config()
    parsed = parse(plain_text_eml)

    out = execute(
        workflow_name="invoice",
        parsed_email=parsed,
        inbox=inbox,
        config=config,
        reply_provider=FakeProvider(),
        dry_run=True,
    )

    assert out["would_call_webhook"] is True
    assert out["payload"]["subject"] == parsed.subject


def test_notify_also_reply_dry_run(plain_text_eml):
    config, inbox = _config()
    parsed = parse(plain_text_eml)

    out = execute(
        workflow_name="urgent",
        parsed_email=parsed,
        inbox=inbox,
        config=config,
        reply_provider=FakeProvider(),
        dry_run=True,
    )

    assert out["would_notify"] is True
    assert out["also_reply"]["would_reply"] is True


def test_reply_flow_calls_mailer(plain_text_eml):
    config, inbox = _config()
    parsed = parse(plain_text_eml)

    with (
        patch("mailagent.core.mailer.send_reply") as send_reply,
        patch("mailagent.core.mailer.save_and_flag_replied") as save_and_flag,
    ):
        send_reply.return_value = object()

        out = execute(
            workflow_name="meeting-request",
            parsed_email=parsed,
            inbox=inbox,
            config=config,
            reply_provider=FakeProvider(),
            dry_run=False,
        )

    assert out["ok"] is True
    send_reply.assert_called_once()
    save_and_flag.assert_called_once()


def test_reply_blocked_by_thread_depth(plain_text_eml):
    config, inbox = _config()
    config.settings.max_thread_replies = 2
    parsed = parse(plain_text_eml)

    thread_ctx = ThreadContext(is_reply=True, is_reply_to_own=True, depth=2)

    out = execute(
        workflow_name="meeting-request",
        parsed_email=parsed,
        inbox=inbox,
        config=config,
        reply_provider=FakeProvider(),
        dry_run=False,
        thread_ctx=thread_ctx,
    )

    assert out["ok"] is True
    assert out["blocked"] is True
    assert out["block_reason"] == "thread_depth_exceeded"


def test_reply_allowed_below_thread_depth(plain_text_eml):
    config, inbox = _config()
    config.settings.max_thread_replies = 3
    parsed = parse(plain_text_eml)

    thread_ctx = ThreadContext(is_reply=True, is_reply_to_own=True, depth=2)

    with (
        patch("mailagent.core.mailer.send_reply") as send_reply,
        patch("mailagent.core.mailer.save_and_flag_replied"),
    ):
        send_reply.return_value = object()

        out = execute(
            workflow_name="meeting-request",
            parsed_email=parsed,
            inbox=inbox,
            config=config,
            reply_provider=FakeProvider(),
            dry_run=False,
            thread_ctx=thread_ctx,
        )

    assert out["ok"] is True
    assert out.get("blocked") is not True


def test_reply_context_includes_thread_history(plain_text_eml):
    config, inbox = _config()
    parsed = parse(plain_text_eml)

    thread_ctx = ThreadContext(
        is_reply=True,
        is_reply_to_own=True,
        depth=1,
        prior_messages=[
            ThreadMessage(
                message_id="<prev@example.com>",
                from_addr="you@example.com",
                date="Mon, 10 Mar 2025",
                body_snippet="Thanks for your meeting request.",
            ),
        ],
    )

    captured_prompt = {}

    class CapturingProvider:
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            captured_prompt["user"] = user_prompt
            return "Got it."

    with (
        patch("mailagent.core.mailer.send_reply") as send_reply,
        patch("mailagent.core.mailer.save_and_flag_replied"),
    ):
        send_reply.return_value = object()

        execute(
            workflow_name="meeting-request",
            parsed_email=parsed,
            inbox=inbox,
            config=config,
            reply_provider=CapturingProvider(),
            dry_run=False,
            thread_ctx=thread_ctx,
        )

    assert "Previous messages in this thread" in captured_prompt["user"]
    assert "Thanks for your meeting request." in captured_prompt["user"]
