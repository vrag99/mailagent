import logging
from typing import Any

import llm
from parser import ParsedEmail

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
You classify incoming emails into exactly one of these categories.
Respond with ONLY the category name. No explanation, no punctuation, no extra text.

Categories:
{categories}"""


def classify(parsed_email: ParsedEmail, workflows: list[dict[str, Any]]) -> str:
    categories = "\n".join(
        f"- {wf['name']}: {wf['match']['intent']}" for wf in workflows
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(categories=categories)

    user_prompt = (
        f"From: {parsed_email.from_addr}\n"
        f"Subject: {parsed_email.subject}\n"
        f"Body:\n{parsed_email.body_truncated}"
    )

    workflow_names = [wf["name"] for wf in workflows]

    try:
        raw = llm.classify(system_prompt, user_prompt)
    except Exception as exc:
        logger.error("LLM classification failed: %s", exc)
        return "fallback"

    result = raw.strip()

    # Exact match
    if result in workflow_names:
        return result

    # Case-insensitive match
    result_lower = result.lower()
    for name in workflow_names:
        if name.lower() == result_lower:
            return name

    logger.warning("Unexpected LLM response %r, falling back to 'fallback'", result)
    return "fallback"
