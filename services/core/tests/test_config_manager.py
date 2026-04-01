from pathlib import Path

import pytest
import yaml

from mailagent.config import (
    Blocklist,
    Config,
    ConfigError,
    ConfigManager,
    Defaults,
    InboxConfig,
    ProviderConfig,
    Settings,
    Workflow,
    WorkflowAction,
    WorkflowMatch,
)


def _make_config() -> Config:
    return Config(
        providers={
            "fast": ProviderConfig(
                name="fast", type="groq", model="llama-3", api_key="key1"
            ),
            "smart": ProviderConfig(
                name="smart", type="openai", model="gpt-4", api_key="key2"
            ),
        },
        defaults=Defaults(classify_provider="fast", reply_provider="smart"),
        inboxes=[
            InboxConfig(
                address="test@example.com",
                credentials={"password": "pass"},
                workflows=[
                    Workflow(
                        name="fallback",
                        match=WorkflowMatch(intent="default"),
                        action=WorkflowAction(type="ignore"),
                    )
                ],
                classify_provider="fast",
                reply_provider="smart",
            )
        ],
        settings=Settings(),
    )


def _make_cm(tmp_path: Path) -> ConfigManager:
    config = _make_config()
    config_path = tmp_path / "mailagent.yml"
    config_path.write_text("", encoding="utf-8")
    return ConfigManager(config, config_path)


class TestInboxCRUD:
    def test_get_inbox(self, tmp_path):
        cm = _make_cm(tmp_path)
        assert cm.get_inbox("test@example.com") is not None
        assert cm.get_inbox("missing@example.com") is None

    def test_get_inbox_case_insensitive(self, tmp_path):
        cm = _make_cm(tmp_path)
        assert cm.get_inbox("TEST@example.com") is not None

    def test_add_inbox(self, tmp_path):
        cm = _make_cm(tmp_path)
        new_inbox = InboxConfig(
            address="new@example.com",
            credentials={"password": "pass2"},
            workflows=[
                Workflow(
                    name="fallback",
                    match=WorkflowMatch(intent="default"),
                    action=WorkflowAction(type="ignore"),
                )
            ],
            classify_provider="fast",
            reply_provider="smart",
        )
        cm.add_inbox(new_inbox)
        assert cm.get_inbox("new@example.com") is not None
        assert len(cm.config.inboxes) == 2

    def test_add_duplicate_inbox_raises(self, tmp_path):
        cm = _make_cm(tmp_path)
        dup = InboxConfig(
            address="test@example.com",
            credentials={"password": "pass"},
            workflows=[],
            classify_provider="fast",
            reply_provider="smart",
        )
        with pytest.raises(ConfigError, match="already exists"):
            cm.add_inbox(dup)

    def test_update_inbox(self, tmp_path):
        cm = _make_cm(tmp_path)
        inbox = cm.get_inbox("test@example.com")
        inbox.name = "Updated"
        cm.update_inbox("test@example.com", inbox)
        assert cm.get_inbox("test@example.com").name == "Updated"

    def test_update_missing_inbox_raises(self, tmp_path):
        cm = _make_cm(tmp_path)
        inbox = InboxConfig(
            address="missing@example.com",
            credentials={"password": "x"},
            workflows=[],
            classify_provider="fast",
            reply_provider="smart",
        )
        with pytest.raises(ConfigError, match="not found"):
            cm.update_inbox("missing@example.com", inbox)

    def test_remove_inbox(self, tmp_path):
        cm = _make_cm(tmp_path)
        cm.remove_inbox("test@example.com")
        assert cm.get_inbox("test@example.com") is None
        assert len(cm.config.inboxes) == 0

    def test_remove_missing_inbox_raises(self, tmp_path):
        cm = _make_cm(tmp_path)
        with pytest.raises(ConfigError, match="not found"):
            cm.remove_inbox("missing@example.com")


class TestProviderCRUD:
    def test_get_provider(self, tmp_path):
        cm = _make_cm(tmp_path)
        assert cm.get_provider("fast") is not None
        assert cm.get_provider("missing") is None

    def test_add_provider(self, tmp_path):
        cm = _make_cm(tmp_path)
        p = ProviderConfig(name="new", type="anthropic", model="claude", api_key="k")
        cm.add_provider("new", p)
        assert cm.get_provider("new") is not None

    def test_add_duplicate_provider_raises(self, tmp_path):
        cm = _make_cm(tmp_path)
        p = ProviderConfig(name="fast", type="groq", model="x", api_key="k")
        with pytest.raises(ConfigError, match="already exists"):
            cm.add_provider("fast", p)

    def test_remove_provider(self, tmp_path):
        cm = _make_cm(tmp_path)
        # Add a third provider that's not referenced, then remove it
        p = ProviderConfig(name="unused", type="groq", model="x", api_key="k")
        cm.add_provider("unused", p)
        cm.remove_provider("unused")
        assert cm.get_provider("unused") is None

    def test_remove_referenced_provider_raises(self, tmp_path):
        cm = _make_cm(tmp_path)
        with pytest.raises(ConfigError, match="referenced by inbox"):
            cm.remove_provider("fast")

    def test_remove_default_provider_raises(self, tmp_path):
        cm = _make_cm(tmp_path)
        # smart is referenced by the inbox, so it fails on inbox check first
        # Remove the inbox so we can test the defaults check
        cm.remove_inbox("test@example.com")
        with pytest.raises(ConfigError, match="default reply_provider"):
            cm.remove_provider("smart")


class TestPersistence:
    def test_persist_writes_valid_yaml(self, tmp_path):
        cm = _make_cm(tmp_path)
        new_inbox = InboxConfig(
            address="new@example.com",
            credentials={"password": "pass2"},
            workflows=[
                Workflow(
                    name="fallback",
                    match=WorkflowMatch(intent="default"),
                    action=WorkflowAction(type="ignore"),
                )
            ],
            classify_provider="fast",
            reply_provider="smart",
        )
        cm.add_inbox(new_inbox)

        config_path = tmp_path / "mailagent.yml"
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

        assert "providers" in raw
        assert "defaults" in raw
        assert "inboxes" in raw
        assert len(raw["inboxes"]) == 2
        assert raw["inboxes"][1]["address"] == "new@example.com"
