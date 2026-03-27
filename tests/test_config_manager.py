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
    _config_to_raw,
)


def _make_config() -> Config:
    return Config(
        providers={
            "fast": ProviderConfig(
                name="fast", type="groq", model="llama-3.3", api_key="sk-123"
            )
        },
        defaults=Defaults(classify_provider="fast", reply_provider="fast"),
        inboxes=[
            InboxConfig(
                address="you@example.com",
                credentials={"password": "secret"},
                workflows=[
                    Workflow(
                        name="support",
                        match=WorkflowMatch(intent="support request"),
                        action=WorkflowAction(type="reply", prompt="Help the user"),
                    ),
                    Workflow(
                        name="fallback",
                        match=WorkflowMatch(intent="default"),
                        action=WorkflowAction(type="ignore"),
                    ),
                ],
                classify_provider="fast",
                reply_provider="fast",
            )
        ],
        settings=Settings(),
    )


def _make_manager(tmp_path: Path) -> ConfigManager:
    config = _make_config()
    path = tmp_path / "mailagent.yml"
    raw = _config_to_raw(config)
    path.write_text(yaml.dump(raw), encoding="utf-8")
    return ConfigManager(config, path)


class TestConfigToRaw:
    def test_roundtrip_preserves_structure(self):
        config = _make_config()
        raw = _config_to_raw(config)

        assert "fast" in raw["providers"]
        assert raw["providers"]["fast"]["type"] == "groq"
        assert raw["defaults"]["classify_provider"] == "fast"
        assert len(raw["inboxes"]) == 1
        assert raw["inboxes"][0]["address"] == "you@example.com"
        assert len(raw["inboxes"][0]["workflows"]) == 2

    def test_default_settings_omitted(self):
        config = _make_config()
        raw = _config_to_raw(config)
        assert "settings" not in raw or raw["settings"] == {}

    def test_non_default_settings_included(self):
        config = _make_config()
        config.settings.api_port = 9090
        raw = _config_to_raw(config)
        assert raw["settings"]["api_port"] == 9090

    def test_valid_yaml_output(self):
        config = _make_config()
        raw = _config_to_raw(config)
        yaml_str = yaml.dump(raw, default_flow_style=False)
        reparsed = yaml.safe_load(yaml_str)
        assert reparsed["providers"]["fast"]["model"] == "llama-3.3"


class TestConfigManagerInbox:
    def test_get_inbox(self, tmp_path):
        cm = _make_manager(tmp_path)
        inbox = cm.get_inbox("you@example.com")
        assert inbox is not None
        assert inbox.address == "you@example.com"

    def test_get_inbox_case_insensitive(self, tmp_path):
        cm = _make_manager(tmp_path)
        inbox = cm.get_inbox("You@Example.Com")
        assert inbox is not None

    def test_get_inbox_not_found(self, tmp_path):
        cm = _make_manager(tmp_path)
        assert cm.get_inbox("missing@example.com") is None

    def test_add_inbox(self, tmp_path):
        cm = _make_manager(tmp_path)
        new_inbox = InboxConfig(
            address="new@example.com",
            credentials={"password": "pw"},
            workflows=[
                Workflow(
                    name="fb",
                    match=WorkflowMatch(intent="default"),
                    action=WorkflowAction(type="ignore"),
                )
            ],
            classify_provider="fast",
            reply_provider="fast",
        )
        cm.add_inbox(new_inbox)

        assert len(cm.config.inboxes) == 2
        assert cm.get_inbox("new@example.com") is not None

    def test_add_inbox_persists_to_yaml(self, tmp_path):
        cm = _make_manager(tmp_path)
        new_inbox = InboxConfig(
            address="new@example.com",
            credentials={"password": "pw"},
            workflows=[
                Workflow(
                    name="fb",
                    match=WorkflowMatch(intent="default"),
                    action=WorkflowAction(type="ignore"),
                )
            ],
            classify_provider="fast",
            reply_provider="fast",
        )
        cm.add_inbox(new_inbox)

        written = (tmp_path / "mailagent.yml").read_text()
        assert "new@example.com" in written

    def test_add_duplicate_inbox_raises(self, tmp_path):
        cm = _make_manager(tmp_path)
        dup = InboxConfig(
            address="you@example.com",
            credentials={"password": "pw"},
            workflows=[
                Workflow(
                    name="fb",
                    match=WorkflowMatch(intent="default"),
                    action=WorkflowAction(type="ignore"),
                )
            ],
            classify_provider="fast",
            reply_provider="fast",
        )
        with pytest.raises(ConfigError, match="already exists"):
            cm.add_inbox(dup)

    def test_update_inbox(self, tmp_path):
        cm = _make_manager(tmp_path)
        inbox = cm.get_inbox("you@example.com")
        inbox.name = "Updated Name"
        cm.update_inbox("you@example.com", inbox)

        updated = cm.get_inbox("you@example.com")
        assert updated.name == "Updated Name"

    def test_update_inbox_not_found(self, tmp_path):
        cm = _make_manager(tmp_path)
        inbox = cm.config.inboxes[0]
        with pytest.raises(ConfigError, match="not found"):
            cm.update_inbox("missing@example.com", inbox)

    def test_remove_inbox(self, tmp_path):
        cm = _make_manager(tmp_path)
        cm.remove_inbox("you@example.com")
        assert len(cm.config.inboxes) == 0
        assert cm.get_inbox("you@example.com") is None

    def test_remove_inbox_not_found(self, tmp_path):
        cm = _make_manager(tmp_path)
        with pytest.raises(ConfigError, match="not found"):
            cm.remove_inbox("missing@example.com")


class TestConfigManagerProvider:
    def test_get_provider(self, tmp_path):
        cm = _make_manager(tmp_path)
        p = cm.get_provider("fast")
        assert p is not None
        assert p.type == "groq"

    def test_get_provider_not_found(self, tmp_path):
        cm = _make_manager(tmp_path)
        assert cm.get_provider("missing") is None

    def test_add_provider(self, tmp_path):
        cm = _make_manager(tmp_path)
        new_provider = ProviderConfig(
            name="smart", type="anthropic", model="claude-sonnet-4-20250514", api_key="sk-456"
        )
        cm.add_provider("smart", new_provider)

        assert "smart" in cm.config.providers
        assert cm.config.providers["smart"].type == "anthropic"

    def test_add_duplicate_provider_raises(self, tmp_path):
        cm = _make_manager(tmp_path)
        dup = ProviderConfig(name="fast", type="groq", model="x", api_key="y")
        with pytest.raises(ConfigError, match="already exists"):
            cm.add_provider("fast", dup)

    def test_update_provider(self, tmp_path):
        cm = _make_manager(tmp_path)
        updated = ProviderConfig(
            name="fast", type="groq", model="new-model", api_key="sk-999"
        )
        cm.update_provider("fast", updated)
        assert cm.config.providers["fast"].model == "new-model"

    def test_update_provider_not_found(self, tmp_path):
        cm = _make_manager(tmp_path)
        p = ProviderConfig(name="x", type="groq", model="x", api_key="x")
        with pytest.raises(ConfigError, match="not found"):
            cm.update_provider("missing", p)

    def test_remove_provider(self, tmp_path):
        cm = _make_manager(tmp_path)
        # First remove inbox referencing the provider
        cm.remove_inbox("you@example.com")
        # Update defaults to not reference it
        cm.config.defaults.classify_provider = ""
        cm.config.defaults.reply_provider = ""
        # Now we need a different default, so add another provider first
        cm.add_provider("other", ProviderConfig(name="other", type="openai", model="gpt-4o", api_key="k"))
        cm.config.defaults.classify_provider = "other"
        cm.config.defaults.reply_provider = "other"
        cm.remove_provider("fast")
        assert "fast" not in cm.config.providers

    def test_remove_provider_in_use_raises(self, tmp_path):
        cm = _make_manager(tmp_path)
        with pytest.raises(ConfigError, match="still referenced"):
            cm.remove_provider("fast")

    def test_remove_default_provider_raises(self, tmp_path):
        cm = _make_manager(tmp_path)
        # Remove inbox so provider isn't referenced by inbox, but still used as default
        cm.remove_inbox("you@example.com")
        with pytest.raises(ConfigError, match="used as default"):
            cm.remove_provider("fast")
