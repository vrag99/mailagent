import os
import time
import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CLASSIFY_MODEL = os.environ.get("CLASSIFY_MODEL", "google/gemini-flash-1.5")
REPLY_MODEL = os.environ.get("REPLY_MODEL", "anthropic/claude-sonnet-4")
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")


def _call(system_prompt: str, user_prompt: str, model: str) -> str:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 500,
    }

    for attempt in range(2):
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(OPENROUTER_URL, headers=headers, json=payload)
            if resp.status_code >= 500:
                if attempt == 0:
                    time.sleep(2)
                    continue
                resp.raise_for_status()
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            if attempt == 0:
                time.sleep(2)
                continue
            raise

    raise RuntimeError("LLM call failed after retries")


def classify(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    return _call(system_prompt, user_prompt, model or CLASSIFY_MODEL)


def generate_reply(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    return _call(system_prompt, user_prompt, model or REPLY_MODEL)
