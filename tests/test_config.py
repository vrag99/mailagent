from pathlib import Path

import pytest

from mailagent.config import ConfigError, load_config


def _write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "mailagent.yml"
    path.write_text(text, encoding="utf-8")
    return path


def _minimal_config() -> str:
    return """
providers:
  fast:
    type: groq
    model: llama-3.3-70b-versatile
    api_key: ${GROQ_API_KEY}

defaults:
  classify_provider: fast
  reply_provider: fast

inboxes:
  - address: you@example.com
    credentials:
      password: ${MAIL_PASSWORD}
    workflows:
      - name: fallback
        match:
          intent: default
        action:
          type: ignore
"""


def test_valid_config_parses(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "key")
    monkeypatch.setenv("MAIL_PASSWORD", "pass")

    path = _write_config(tmp_path, _minimal_config())
    result = load_config(path)

    assert result.config.defaults.classify_provider == "fast"
    assert len(result.config.inboxes) == 1
    assert result.config.inboxes[0].address == "you@example.com"


def test_missing_env_var_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("MAIL_PASSWORD", "pass")

    path = _write_config(tmp_path, _minimal_config())

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert "Environment variable GROQ_API_KEY is not set" in str(exc.value)


def test_invalid_provider_reference_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "key")
    monkeypatch.setenv("MAIL_PASSWORD", "pass")

    config = _minimal_config().replace(
        "classify_provider: fast", "classify_provider: missing"
    )
    path = _write_config(tmp_path, config)

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert "defaults.classify_provider references undefined provider 'missing'" in str(
        exc.value
    )


def test_auto_add_fallback_warns(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "key")
    monkeypatch.setenv("MAIL_PASSWORD", "pass")

    config = """
providers:
  fast:
    type: groq
    model: llama-3.3-70b-versatile
    api_key: ${GROQ_API_KEY}

defaults:
  classify_provider: fast
  reply_provider: fast

inboxes:
  - address: you@example.com
    credentials:
      password: ${MAIL_PASSWORD}
    workflows:
      - name: only
        match:
          intent: something
        action:
          type: ignore
"""

    path = _write_config(tmp_path, config)
    result = load_config(path)

    assert result.config.inboxes[0].workflows[-1].name == "fallback"
    assert any("auto-adding fallback" in warning for warning in result.warnings)


def test_duplicate_inbox_address_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "key")
    monkeypatch.setenv("MAIL_PASSWORD", "pass")

    config = """
providers:
  fast:
    type: groq
    model: llama-3.3-70b-versatile
    api_key: ${GROQ_API_KEY}

defaults:
  classify_provider: fast
  reply_provider: fast

inboxes:
  - address: you@example.com
    credentials:
      password: ${MAIL_PASSWORD}
    workflows:
      - name: fallback
        match:
          intent: default
        action:
          type: ignore
  - address: you@example.com
    credentials:
      password: ${MAIL_PASSWORD}
    workflows:
      - name: fallback
        match:
          intent: default
        action:
          type: ignore
"""

    path = _write_config(tmp_path, config)

    with pytest.raises(ConfigError) as exc:
        load_config(path)

    assert "duplicate inbox address" in str(exc.value)
