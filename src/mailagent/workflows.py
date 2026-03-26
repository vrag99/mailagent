from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from . import mailer
from .config import Config, InboxConfig, Workflow, WorkflowAction
from .parser import ParsedEmail
from .providers import BaseProvider
from .state import ThreadContext, ThreadState

logger = logging.getLogger(__name__)

_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def execute(
    workflow_name: str,
    parsed_email: ParsedEmail,
    inbox: InboxConfig,
    config: Config,
    reply_provider: BaseProvider,
    dry_run: bool = False,
    thread_ctx: ThreadContext | None = None,
    thread_state: ThreadState | None = None,
) -> dict[str, Any]:
    workflow = _find_workflow(inbox.workflows, workflow_name)
    if workflow is None:
        logger.error("No workflow named %r for inbox %s", workflow_name, inbox.address)
        return {"ok": False, "reason": "workflow_not_found"}

    action = workflow.action
    preview: dict[str, Any] = {
        "ok": True,
        "dry_run": dry_run,
        "workflow": workflow.name,
        "action": action.type,
    }

    if action.type == "ignore":
        logger.info(
            "Ignored: %r from %s (workflow: %s)",
            parsed_email.subject,
            parsed_email.from_addr,
            workflow.name,
        )
        return preview

    if action.type == "reply":
        result = _perform_reply(
            workflow, parsed_email, inbox, config, reply_provider, dry_run=dry_run,
            thread_ctx=thread_ctx, thread_state=thread_state,
        )
        preview.update(result)
        if action.also_webhook and action.webhook_url:
            webhook_result = _perform_notify(
                webhook_url=action.webhook_url,
                workflow_name=workflow.name,
                parsed_email=parsed_email,
                dry_run=dry_run,
            )
            preview["also_webhook"] = webhook_result
        return preview

    if action.type == "notify":
        notify_result = _perform_notify(
            webhook_url=action.webhook or "",
            workflow_name=workflow.name,
            parsed_email=parsed_email,
            dry_run=dry_run,
        )
        preview.update(notify_result)
        if action.also_reply:
            if not action.prompt:
                preview["also_reply"] = {"ok": False, "reason": "missing_prompt"}
            else:
                preview["also_reply"] = _perform_reply(
                    workflow,
                    parsed_email,
                    inbox,
                    config,
                    reply_provider,
                    dry_run=dry_run,
                    override_prompt=action.prompt,
                    thread_ctx=thread_ctx,
                    thread_state=thread_state,
                )
        return preview

    if action.type == "webhook":
        webhook_result = _perform_webhook_action(
            action, parsed_email, workflow.name, dry_run=dry_run
        )
        preview.update(webhook_result)
        return preview

    logger.warning("Unknown action type %r for workflow %r", action.type, workflow.name)
    preview.update({"ok": False, "reason": "unknown_action_type"})
    return preview


def _perform_reply(
    workflow: Workflow,
    parsed_email: ParsedEmail,
    inbox: InboxConfig,
    config: Config,
    reply_provider: BaseProvider,
    dry_run: bool,
    override_prompt: str | None = None,
    thread_ctx: ThreadContext | None = None,
    thread_state: ThreadState | None = None,
) -> dict[str, Any]:
    block_reason = _block_reason(parsed_email, inbox, thread_ctx, config)
    if block_reason:
        logger.info(
            "Reply blocked (%s): from=%s subject=%r",
            block_reason,
            parsed_email.from_email,
            parsed_email.subject,
        )
        return {"ok": True, "blocked": True, "block_reason": block_reason}

    prompt = override_prompt or workflow.action.prompt
    if not prompt:
        logger.warning("Reply workflow %r has no prompt", workflow.name)
        return {"ok": False, "reason": "missing_prompt"}

    context_prompt = ""

    # Add thread history when replying to own thread
    if thread_ctx and thread_ctx.is_reply_to_own:
        if thread_ctx.prior_messages is None:
            thread_ctx.prior_messages = mailer.fetch_thread_messages(
                references=parsed_email.references,
                mail_host=config.settings.mail_host,
                inbox_address=inbox.address,
                password=inbox.credentials["password"],
                max_messages=config.settings.thread_history_max,
            )
        if thread_ctx.prior_messages:
            history_parts = ["Previous messages in this thread (oldest first):\n"]
            for i, msg in enumerate(thread_ctx.prior_messages, 1):
                history_parts.append(
                    f"[{i}] From: {msg.from_addr} ({msg.date})\n{msg.body_snippet}\n"
                )
            history_text = "\n".join(history_parts)
            # Cap thread history at configured limit
            if len(history_text) > config.settings.thread_context_limit:
                history_text = history_text[: config.settings.thread_context_limit] + "\n[...truncated]"
            context_prompt += history_text + "\nYou are replying to the latest message above.\n"

    context_prompt += (
        "You are replying to this email.\n"
        f"From: {parsed_email.from_addr}\n"
        f"Subject: {parsed_email.subject}\n"
        f"Date: {parsed_email.date}\n"
        f"Body:\n{parsed_email.body_plain[: config.settings.reply_body_limit]}\n"
    )

    system_prompt = _merge_prompts(inbox.system_prompt, prompt)

    if dry_run:
        return {
            "ok": True,
            "blocked": False,
            "would_reply": True,
            "system_prompt_preview": system_prompt[:300],
        }

    try:
        reply_text = reply_provider.generate(
            system_prompt=system_prompt, user_prompt=context_prompt
        )
    except Exception as exc:
        logger.error("Failed to generate reply for workflow %s: %s", workflow.name, exc)
        return {"ok": False, "reason": "reply_generation_failed", "error": str(exc)}

    password = inbox.credentials["password"]
    mail_host = config.settings.mail_host
    try:
        reply_msg = mailer.send_reply(
            original=parsed_email,
            body_text=reply_text,
            mail_host=mail_host,
            inbox_address=inbox.address,
            password=password,
            inbox_name=inbox.name,
        )
        mailer.save_and_flag_replied(
            reply_msg=reply_msg,
            original=parsed_email,
            mail_host=mail_host,
            inbox_address=inbox.address,
            password=password,
        )
    except Exception as exc:
        logger.error(
            "Failed to send/save/flag reply for workflow %s: %s", workflow.name, exc
        )
        return {"ok": False, "reason": "reply_delivery_failed", "error": str(exc)}

    # Record outgoing Message-ID for thread tracking
    if thread_state and reply_msg.get("Message-ID"):
        thread_state.record_sent(reply_msg["Message-ID"], parsed_email.message_id)

    logger.info("Replied to %r from %s", parsed_email.subject, parsed_email.from_addr)
    return {"ok": True, "blocked": False, "replied": True}


def _perform_notify(
    webhook_url: str,
    workflow_name: str,
    parsed_email: ParsedEmail,
    dry_run: bool,
) -> dict[str, Any]:
    if not webhook_url:
        logger.warning(
            "Notify workflow %r has no webhook URL configured", workflow_name
        )
        return {"ok": False, "reason": "missing_webhook"}

    payload = {
        "from": parsed_email.from_addr,
        "subject": parsed_email.subject,
        "date": parsed_email.date,
        "summary": parsed_email.body_plain[:500],
        "workflow": workflow_name,
    }

    if dry_run:
        return {
            "ok": True,
            "would_notify": True,
            "webhook_url": webhook_url,
            "payload": payload,
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(webhook_url, json=payload)
            response.raise_for_status()
    except Exception as exc:
        logger.error("Notify webhook failed for workflow %s: %s", workflow_name, exc)
        return {"ok": False, "reason": "notify_failed", "error": str(exc)}

    logger.info(
        "Notified webhook for workflow %s and subject %r",
        workflow_name,
        parsed_email.subject,
    )
    return {"ok": True, "notified": True}


def _perform_webhook_action(
    action: WorkflowAction,
    parsed_email: ParsedEmail,
    workflow_name: str,
    dry_run: bool,
) -> dict[str, Any]:
    if not action.url:
        return {"ok": False, "reason": "missing_url"}

    payload = _render_value(
        action.payload or _default_payload(parsed_email), parsed_email
    )
    headers = _render_value(action.headers or {}, parsed_email)
    method = (action.method or "POST").upper()

    if dry_run:
        return {
            "ok": True,
            "would_call_webhook": True,
            "url": action.url,
            "method": method,
            "headers": headers,
            "payload": payload,
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.request(method, action.url, headers=headers, json=payload)
            response.raise_for_status()
    except Exception as exc:
        logger.error("Webhook action failed for workflow %s: %s", workflow_name, exc)
        return {"ok": False, "reason": "webhook_failed", "error": str(exc)}

    logger.info("Webhook action sent for workflow %s", workflow_name)
    return {"ok": True, "webhook_sent": True}


def _find_workflow(workflows: list[Workflow], workflow_name: str) -> Workflow | None:
    for workflow in workflows:
        if workflow.name == workflow_name:
            return workflow
    for workflow in workflows:
        if workflow.match.intent.lower() == "default":
            return workflow
    return None


def _block_reason(
    parsed_email: ParsedEmail,
    inbox: InboxConfig,
    thread_ctx: ThreadContext | None = None,
    config: Config | None = None,
) -> str | None:
    if parsed_email.from_email.lower() == inbox.address.lower():
        return "self_address"

    if thread_ctx and config:
        max_replies = config.settings.max_thread_replies
        if thread_ctx.depth >= max_replies:
            return "thread_depth_exceeded"

    blocklist = inbox.blocklist
    if not blocklist:
        return None

    from_email = parsed_email.from_email.lower()
    for pattern in blocklist.from_patterns:
        if pattern.lower() in from_email:
            return f"from_pattern:{pattern}"

    for header in blocklist.headers:
        if ":" in header:
            header_name, header_value = header.split(":", 1)
            header_name = header_name.strip()
            header_value = header_value.strip().lower()
            actual = parsed_email.raw_msg.get(header_name)
            if actual and header_value in actual.lower():
                return f"header:{header}"
        else:
            if parsed_email.raw_msg.get(header.strip()):
                return f"header:{header}"

    return None


def _default_payload(parsed_email: ParsedEmail) -> dict[str, Any]:
    return {
        "from": parsed_email.from_addr,
        "subject": parsed_email.subject,
        "date": parsed_email.date,
        "body": parsed_email.body_plain,
    }


def _render_value(value: Any, parsed_email: ParsedEmail) -> Any:
    if isinstance(value, str):
        return _render_template(value, parsed_email)
    if isinstance(value, dict):
        return {k: _render_value(v, parsed_email) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_value(item, parsed_email) for item in value]
    return value


def _render_template(value: str, parsed_email: ParsedEmail) -> str:
    vars_map = {
        "from": parsed_email.from_addr,
        "from_email": parsed_email.from_email,
        "to": parsed_email.to_addr,
        "subject": parsed_email.subject,
        "date": parsed_email.date,
        "body": parsed_email.body_plain,
        "body_truncated": parsed_email.body_truncated,
        "message_id": parsed_email.message_id,
    }

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(vars_map.get(key, match.group(0)))

    return _TEMPLATE_RE.sub(_replace, value)


def _merge_prompts(base: str | None, extra: str | None) -> str:
    left = (base or "").strip()
    right = (extra or "").strip()

    if left and right:
        return f"{left}\n\n{right}"
    if right:
        return right
    return left
