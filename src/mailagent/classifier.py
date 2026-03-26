from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .config import Workflow
from .parser import ParsedEmail
from .providers import BaseProvider, ProviderError
from .state import ThreadContext

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    workflow_name: str
    method: str
    confidence: float | None = None


def classify(
    email: ParsedEmail,
    workflows: list[Workflow],
    provider: BaseProvider,
    system_prompt: str,
    thread_ctx: ThreadContext | None = None,
) -> ClassificationResult:
    """
    Classify an email into a workflow.

    Strategy:
    1. Try LLM classification.
    2. If LLM fails (API error, garbled response), fall back to keyword matching.
    3. If keywords also don't match, return "fallback".
    """
    try:
        result = _classify_llm(email, workflows, provider, system_prompt, thread_ctx=thread_ctx)
        if result:
            return result
    except ProviderError as exc:
        logger.warning("LLM classification failed: %s. Falling back to keywords.", exc)

    result = _classify_keywords(email, workflows)
    if result:
        return ClassificationResult(workflow_name=result, method="keyword")

    return ClassificationResult(workflow_name="fallback", method="keyword")


def _classify_llm(
    email: ParsedEmail,
    workflows: list[Workflow],
    provider: BaseProvider,
    system_prompt: str,
    thread_ctx: ThreadContext | None = None,
) -> ClassificationResult | None:
    candidates = [wf for wf in workflows if wf.match.intent.lower() != "default"]
    if not candidates:
        return None

    allowed = [wf.name for wf in candidates]
    options = "\n".join(f"- {wf.name}: {wf.match.intent}" for wf in candidates)

    classify_system = (
        f"{system_prompt}\n\n"
        "You classify incoming emails into exactly one workflow name.\n"
        'Return ONLY JSON in this exact form: {"workflow": "<name>", "confidence": 0.85}.\n'
        "confidence is a float between 0.0 and 1.0 (up to 2 decimal places) reflecting how well the email fits the chosen workflow.\n"
        "Do not add markdown or explanation."
    )
    classify_user = (
        "Workflows:\n"
        f"{options}\n\n"
        f"Allowed workflow names: {', '.join(allowed)}\n\n"
        "Email:\n"
        f"From: {email.from_addr}\n"
        f"Subject: {email.subject}\n"
        f"Body:\n{email.body_truncated}"
    )

    if thread_ctx and thread_ctx.is_reply_to_own:
        classify_user += (
            f"\n\n[Thread context: This is a reply to a message you previously sent. "
            f"Thread depth: {thread_ctx.depth}. "
            f"Consider whether this needs a new response or is a simple acknowledgment.]"
        )

    raw = provider.classify(classify_system, classify_user)
    workflow_name, confidence = _parse_llm_response(raw)
    if workflow_name is None:
        return None

    for name in allowed:
        if name == workflow_name or name.lower() == workflow_name.lower():
            return ClassificationResult(workflow_name=name, method="llm", confidence=confidence)

    logger.warning("LLM returned unknown workflow %r; falling back.", workflow_name)
    return None


def _parse_llm_response(raw: str) -> tuple[str | None, float | None]:
    """Parse LLM classification response. Returns (workflow_name, confidence)."""
    text = raw.strip()
    if not text:
        return None, None

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text, None

    if not isinstance(data, dict):
        return None, None

    workflow = data.get("workflow")
    if not isinstance(workflow, str):
        return None, None

    raw_conf = data.get("confidence")
    confidence: float | None = None
    try:
        val = float(raw_conf)  # type: ignore[arg-type]
        if 0.0 <= val <= 1.0:
            confidence = round(val, 2)
    except (TypeError, ValueError):
        pass

    return workflow.strip(), confidence


def _classify_keywords(email: ParsedEmail, workflows: list[Workflow]) -> str | None:
    text = f"{email.subject}\n{email.body_plain}".lower()

    for workflow in workflows:
        if workflow.match.intent.lower() == "default":
            continue
        keywords = workflow.match.keywords
        if not keywords or (not keywords.any and not keywords.all):
            continue

        any_ok = True
        all_ok = True

        if keywords.any:
            any_ok = any(keyword.lower() in text for keyword in keywords.any)
        if keywords.all:
            all_ok = all(keyword.lower() in text for keyword in keywords.all)

        if any_ok and all_ok:
            return workflow.name

    return None
