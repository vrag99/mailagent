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
from mailagent.parser import parse
from mailagent.workflows import execute


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
        patch("mailagent.mailer.send_reply") as send_reply,
        patch("mailagent.mailer.save_and_flag_replied") as save_and_flag,
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
