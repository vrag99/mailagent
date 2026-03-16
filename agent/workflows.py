import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
import yaml

import llm
import mailer
from parser import ParsedEmail

logger = logging.getLogger(__name__)

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _interpolate(value: str) -> str:
    def replacer(m: re.Match) -> str:
        return os.environ.get(m.group(1), "")
    return _ENV_VAR_RE.sub(replacer, value)


def _interpolate_dict(obj: Any) -> Any:
    if isinstance(obj, str):
        return _interpolate(obj)
    if isinstance(obj, dict):
        return {k: _interpolate_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate_dict(i) for i in obj]
    return obj


@dataclass
class Config:
    inbox: str
    blocklist_from_patterns: list[str]
    blocklist_headers: list[str]
    workflows: list[dict[str, Any]]


def load_config(path: str = "/app/config.yml") -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    raw = _interpolate_dict(raw)
    blocklist = raw.get("blocklist", {})
    return Config(
        inbox=raw["inbox"],
        blocklist_from_patterns=blocklist.get("from_patterns", []),
        blocklist_headers=blocklist.get("headers", []),
        workflows=raw["workflows"],
    )


def _is_blocked(parsed_email: ParsedEmail, config: Config) -> bool:
    own_addr = f"{os.environ.get('MAIL_USER', '')}@{os.environ.get('MAIL_DOMAIN', '')}"

    if parsed_email.from_email == own_addr:
        logger.info("Blocked reply to self: %s", parsed_email.from_email)
        return True

    for pattern in config.blocklist_from_patterns:
        if pattern in parsed_email.from_email:
            logger.info("Blocked reply — from matches pattern %r: %s", pattern, parsed_email.from_email)
            return True

    raw_headers = str(parsed_email.raw_msg)
    for header in config.blocklist_headers:
        header_name = header.split(":")[0].strip()
        if parsed_email.raw_msg.get(header_name):
            logger.info("Blocked reply — header present: %s", header_name)
            return True
        # Also check the full "Header: value" form
        if header.lower() in raw_headers.lower():
            logger.info("Blocked reply — header match: %s", header)
            return True

    return False


def execute(workflow_name: str, parsed_email: ParsedEmail, config: Config) -> None:
    workflow = next((wf for wf in config.workflows if wf["name"] == workflow_name), None)
    if workflow is None:
        logger.error("No workflow named %r", workflow_name)
        return

    action = workflow["action"]
    action_type = action["type"]

    if action_type == "reply":
        if _is_blocked(parsed_email, config):
            return

        user_prompt = (
            f"You are replying to this email:\n"
            f"From: {parsed_email.from_addr}\n"
            f"Subject: {parsed_email.subject}\n"
            f"Body:\n{parsed_email.body_plain}\n\n"
            f"Write your reply now."
        )

        try:
            reply_text = llm.generate_reply(
                system_prompt=action["prompt"],
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.error("Failed to generate reply: %s", exc)
            return

        try:
            reply_msg = mailer.send_reply(parsed_email, reply_text)
        except Exception as exc:
            logger.error("Failed to send reply: %s", exc)
            return

        try:
            mailer.save_to_sent(reply_msg)
        except Exception as exc:
            logger.error("Failed to save to Sent: %s", exc)

        try:
            mailer.flag_original_replied(parsed_email)
        except Exception as exc:
            logger.error("Failed to flag original as answered: %s", exc)

        logger.info("Replied to %r from %s", parsed_email.subject, parsed_email.from_addr)

    elif action_type == "ignore":
        logger.info("Ignored: %r from %s (workflow: %s)", parsed_email.subject, parsed_email.from_addr, workflow_name)

    elif action_type == "notify":
        webhook_url = action.get("webhook", "")
        if not webhook_url:
            logger.warning("Notify workflow %r has no webhook URL configured", workflow_name)
            return

        payload = {
            "from": parsed_email.from_addr,
            "subject": parsed_email.subject,
            "date": parsed_email.date,
            "summary": parsed_email.body_plain[:500],
            "workflow": workflow_name,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(webhook_url, json=payload)
                resp.raise_for_status()
            logger.info("Notified webhook for: %r", parsed_email.subject)
        except Exception as exc:
            logger.error("Webhook POST failed: %s", exc)

    else:
        logger.warning("Unknown action type %r for workflow %r", action_type, workflow_name)
