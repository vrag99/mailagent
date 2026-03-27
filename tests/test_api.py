import pytest
from fastapi.testclient import TestClient

from mailagent.api import create_app
from mailagent.config import (
    Config,
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

import yaml


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


@pytest.fixture
def client(tmp_path):
    config = _make_config()
    path = tmp_path / "mailagent.yml"
    path.write_text(yaml.dump(_config_to_raw(config)), encoding="utf-8")
    cm = ConfigManager(config, path)
    app = create_app(cm)
    return TestClient(app)


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestInboxesAPI:
    def test_list_inboxes(self, client):
        resp = client.get("/api/inboxes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["address"] == "you@example.com"

    def test_get_inbox(self, client):
        resp = client.get("/api/inboxes/you@example.com")
        assert resp.status_code == 200
        assert resp.json()["address"] == "you@example.com"

    def test_get_inbox_not_found(self, client):
        resp = client.get("/api/inboxes/missing@example.com")
        assert resp.status_code == 404

    def test_create_inbox(self, client):
        resp = client.post("/api/inboxes", json={
            "address": "new@example.com",
            "password": "pw123",
            "workflows": [
                {
                    "name": "fallback",
                    "match": {"intent": "default"},
                    "action": {"type": "ignore"},
                }
            ],
        })
        assert resp.status_code == 201
        assert resp.json()["address"] == "new@example.com"

        # Verify it appears in list
        resp = client.get("/api/inboxes")
        assert len(resp.json()) == 2

    def test_create_duplicate_inbox(self, client):
        resp = client.post("/api/inboxes", json={
            "address": "you@example.com",
            "password": "pw",
            "workflows": [
                {
                    "name": "fb",
                    "match": {"intent": "default"},
                    "action": {"type": "ignore"},
                }
            ],
        })
        assert resp.status_code == 409

    def test_create_inbox_invalid_provider(self, client):
        resp = client.post("/api/inboxes", json={
            "address": "new@example.com",
            "password": "pw",
            "classify_provider": "nonexistent",
            "workflows": [
                {
                    "name": "fb",
                    "match": {"intent": "default"},
                    "action": {"type": "ignore"},
                }
            ],
        })
        assert resp.status_code == 400

    def test_update_inbox(self, client):
        resp = client.patch("/api/inboxes/you@example.com", json={
            "name": "Updated Name",
            "system_prompt": "New prompt",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["system_prompt"] == "New prompt"

    def test_update_inbox_not_found(self, client):
        resp = client.patch("/api/inboxes/missing@example.com", json={
            "name": "X",
        })
        assert resp.status_code == 404

    def test_delete_inbox(self, client):
        resp = client.delete("/api/inboxes/you@example.com")
        assert resp.status_code == 204

        resp = client.get("/api/inboxes")
        assert len(resp.json()) == 0

    def test_delete_inbox_not_found(self, client):
        resp = client.delete("/api/inboxes/missing@example.com")
        assert resp.status_code == 404


class TestProvidersAPI:
    def test_list_providers(self, client):
        resp = client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "fast"
        # api_key should NOT be in the response
        assert "api_key" not in data[0]

    def test_get_provider(self, client):
        resp = client.get("/api/providers/fast")
        assert resp.status_code == 200
        assert resp.json()["type"] == "groq"

    def test_get_provider_not_found(self, client):
        resp = client.get("/api/providers/missing")
        assert resp.status_code == 404

    def test_create_provider(self, client):
        resp = client.post("/api/providers/smart", json={
            "type": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "api_key": "sk-ant-123",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "smart"
        assert resp.json()["type"] == "anthropic"

    def test_create_duplicate_provider(self, client):
        resp = client.post("/api/providers/fast", json={
            "type": "groq",
            "model": "x",
            "api_key": "y",
        })
        assert resp.status_code == 409

    def test_create_provider_invalid_type(self, client):
        resp = client.post("/api/providers/bad", json={
            "type": "invalid_provider",
            "model": "x",
            "api_key": "y",
        })
        assert resp.status_code == 400

    def test_update_provider(self, client):
        resp = client.put("/api/providers/fast", json={
            "type": "groq",
            "model": "new-model",
            "api_key": "sk-new",
        })
        assert resp.status_code == 200
        assert resp.json()["model"] == "new-model"

    def test_delete_provider_in_use(self, client):
        resp = client.delete("/api/providers/fast")
        assert resp.status_code == 400
        assert "referenced" in resp.json()["detail"] or "used as default" in resp.json()["detail"]


class TestWorkflowsAPI:
    def test_list_workflows(self, client):
        resp = client.get("/api/inboxes/you@example.com/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "support"
        assert data[1]["name"] == "fallback"

    def test_list_workflows_inbox_not_found(self, client):
        resp = client.get("/api/inboxes/missing@example.com/workflows")
        assert resp.status_code == 404

    def test_get_workflow(self, client):
        resp = client.get("/api/inboxes/you@example.com/workflows/support")
        assert resp.status_code == 200
        assert resp.json()["name"] == "support"
        assert resp.json()["action"]["type"] == "reply"

    def test_get_workflow_not_found(self, client):
        resp = client.get("/api/inboxes/you@example.com/workflows/missing")
        assert resp.status_code == 404

    def test_create_workflow(self, client):
        resp = client.post("/api/inboxes/you@example.com/workflows", json={
            "name": "billing",
            "match": {"intent": "billing question"},
            "action": {"type": "reply", "prompt": "Help with billing"},
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "billing"

        # Verify it appears in list
        resp = client.get("/api/inboxes/you@example.com/workflows")
        assert len(resp.json()) == 3

    def test_create_duplicate_workflow(self, client):
        resp = client.post("/api/inboxes/you@example.com/workflows", json={
            "name": "support",
            "match": {"intent": "x"},
            "action": {"type": "ignore"},
        })
        assert resp.status_code == 409

    def test_update_workflow(self, client):
        resp = client.put("/api/inboxes/you@example.com/workflows/support", json={
            "name": "support",
            "match": {"intent": "updated intent"},
            "action": {"type": "reply", "prompt": "Updated prompt"},
        })
        assert resp.status_code == 200
        assert resp.json()["match"]["intent"] == "updated intent"

    def test_update_workflow_not_found(self, client):
        resp = client.put("/api/inboxes/you@example.com/workflows/missing", json={
            "name": "missing",
            "match": {"intent": "x"},
            "action": {"type": "ignore"},
        })
        assert resp.status_code == 404

    def test_delete_workflow(self, client):
        resp = client.delete("/api/inboxes/you@example.com/workflows/support")
        assert resp.status_code == 204

        resp = client.get("/api/inboxes/you@example.com/workflows")
        assert len(resp.json()) == 1

    def test_delete_last_workflow_blocked(self, client):
        # Delete first, leaving one
        client.delete("/api/inboxes/you@example.com/workflows/support")
        # Try to delete the last one
        resp = client.delete("/api/inboxes/you@example.com/workflows/fallback")
        assert resp.status_code == 400
        assert "last workflow" in resp.json()["detail"]
