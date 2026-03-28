"""API integration tests using the YAML fixture config (fixtures/api_config.yml).

The api_client fixture loads the real config through load_config(), so
schema validation, env interpolation, and default merging all run — just
like production.
"""

import yaml
import pytest

httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi.testclient")


class TestHealth:
    def test_health(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestInboxes:
    def test_list_inboxes(self, api_client):
        resp = api_client.get("/api/inboxes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["address"] == "test@example.com"
        assert data[0]["name"] == "Test Inbox"

    def test_get_inbox(self, api_client):
        resp = api_client.get("/api/inboxes/test@example.com")
        assert resp.status_code == 200
        body = resp.json()
        assert body["address"] == "test@example.com"
        assert body["classify_provider"] == "fast"
        assert body["reply_provider"] == "smart"
        assert len(body["workflows"]) == 2  # support + fallback

    def test_get_inbox_not_found(self, api_client):
        resp = api_client.get("/api/inboxes/missing@example.com")
        assert resp.status_code == 404

    def test_create_inbox(self, api_client):
        resp = api_client.post(
            "/api/inboxes",
            json={
                "address": "new@example.com",
                "password": "pass",
                "workflows": [
                    {
                        "name": "catchall",
                        "match": {"intent": "default"},
                        "action": {"type": "ignore"},
                    }
                ],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["address"] == "new@example.com"
        # Should inherit default providers
        assert body["classify_provider"] == "fast"
        assert body["reply_provider"] == "smart"

        # Verify it shows up in the list
        resp2 = api_client.get("/api/inboxes")
        assert len(resp2.json()) == 2

    def test_create_inbox_with_explicit_providers(self, api_client):
        resp = api_client.post(
            "/api/inboxes",
            json={
                "address": "custom@example.com",
                "password": "pass",
                "classify_provider": "smart",
                "reply_provider": "fast",
                "workflows": [
                    {
                        "name": "fallback",
                        "match": {"intent": "default"},
                        "action": {"type": "ignore"},
                    }
                ],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["classify_provider"] == "smart"
        assert body["reply_provider"] == "fast"

    def test_create_inbox_unknown_provider(self, api_client):
        resp = api_client.post(
            "/api/inboxes",
            json={
                "address": "bad@example.com",
                "password": "pass",
                "classify_provider": "nonexistent",
                "workflows": [
                    {
                        "name": "fallback",
                        "match": {"intent": "default"},
                        "action": {"type": "ignore"},
                    }
                ],
            },
        )
        assert resp.status_code == 400
        assert "nonexistent" in resp.json()["detail"]

    def test_create_duplicate_inbox(self, api_client):
        resp = api_client.post(
            "/api/inboxes",
            json={
                "address": "test@example.com",
                "password": "pass",
                "workflows": [
                    {
                        "name": "fallback",
                        "match": {"intent": "default"},
                        "action": {"type": "ignore"},
                    }
                ],
            },
        )
        assert resp.status_code == 409

    def test_update_inbox(self, api_client):
        resp = api_client.patch(
            "/api/inboxes/test@example.com",
            json={"name": "Updated Name", "system_prompt": "Be concise."},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Updated Name"
        assert body["system_prompt"] == "Be concise."

    def test_update_inbox_not_found(self, api_client):
        resp = api_client.patch(
            "/api/inboxes/ghost@example.com",
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    def test_delete_inbox(self, api_client):
        resp = api_client.delete("/api/inboxes/test@example.com")
        assert resp.status_code == 204

        resp2 = api_client.get("/api/inboxes")
        assert len(resp2.json()) == 0

    def test_delete_inbox_not_found(self, api_client):
        resp = api_client.delete("/api/inboxes/ghost@example.com")
        assert resp.status_code == 404


class TestProviders:
    def test_list_providers(self, api_client):
        resp = api_client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        names = {p["name"] for p in data}
        assert names == {"fast", "smart"}
        # api_key must NOT leak
        for p in data:
            assert "api_key" not in p

    def test_get_provider(self, api_client):
        resp = api_client.get("/api/providers/fast")
        assert resp.status_code == 200
        assert resp.json()["type"] == "groq"

    def test_get_provider_not_found(self, api_client):
        resp = api_client.get("/api/providers/missing")
        assert resp.status_code == 404

    def test_create_provider(self, api_client):
        resp = api_client.post(
            "/api/providers/cheap",
            json={
                "type": "groq",
                "model": "llama-3.1-8b",
                "api_key": "sk-test",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "cheap"

    def test_create_duplicate_provider(self, api_client):
        resp = api_client.post(
            "/api/providers/fast",
            json={"type": "groq", "model": "x", "api_key": "k"},
        )
        assert resp.status_code == 409

    def test_update_provider(self, api_client):
        resp = api_client.put(
            "/api/providers/fast",
            json={
                "type": "groq",
                "model": "llama-3.3-70b-versatile",
                "api_key": "new-key",
                "timeout": 60,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["timeout"] == 60

    def test_update_provider_not_found(self, api_client):
        resp = api_client.put(
            "/api/providers/ghost",
            json={"type": "groq", "model": "x", "api_key": "k"},
        )
        assert resp.status_code == 404

    def test_delete_referenced_provider(self, api_client):
        resp = api_client.delete("/api/providers/fast")
        assert resp.status_code == 400
        assert "referenced" in resp.json()["detail"]

    def test_delete_unreferenced_provider(self, api_client):
        # Create a new provider, then delete it
        api_client.post(
            "/api/providers/temp",
            json={"type": "groq", "model": "x", "api_key": "k"},
        )
        resp = api_client.delete("/api/providers/temp")
        assert resp.status_code == 204


class TestWorkflows:
    def test_list_workflows(self, api_client):
        resp = api_client.get("/api/inboxes/test@example.com/workflows")
        assert resp.status_code == 200
        names = [w["name"] for w in resp.json()]
        assert "support" in names
        assert "fallback" in names

    def test_list_workflows_inbox_not_found(self, api_client):
        resp = api_client.get("/api/inboxes/ghost@example.com/workflows")
        assert resp.status_code == 404

    def test_get_workflow(self, api_client):
        resp = api_client.get("/api/inboxes/test@example.com/workflows/support")
        assert resp.status_code == 200
        body = resp.json()
        assert body["action"]["type"] == "reply"
        assert body["match"]["keywords"]["any"] == ["help", "issue", "bug"]

    def test_get_workflow_not_found(self, api_client):
        resp = api_client.get("/api/inboxes/test@example.com/workflows/nope")
        assert resp.status_code == 404

    def test_create_workflow(self, api_client):
        resp = api_client.post(
            "/api/inboxes/test@example.com/workflows",
            json={
                "name": "billing",
                "match": {"intent": "billing inquiry"},
                "action": {"type": "reply", "prompt": "Handle billing."},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "billing"

        # Verify it shows up
        resp2 = api_client.get("/api/inboxes/test@example.com/workflows")
        names = [w["name"] for w in resp2.json()]
        assert "billing" in names

    def test_create_duplicate_workflow(self, api_client):
        resp = api_client.post(
            "/api/inboxes/test@example.com/workflows",
            json={
                "name": "fallback",
                "match": {"intent": "default"},
                "action": {"type": "ignore"},
            },
        )
        assert resp.status_code == 409

    def test_replace_workflow(self, api_client):
        resp = api_client.put(
            "/api/inboxes/test@example.com/workflows/support",
            json={
                "name": "support",
                "match": {"intent": "help request"},
                "action": {"type": "reply", "prompt": "Updated prompt."},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["action"]["prompt"] == "Updated prompt."

    def test_replace_workflow_not_found(self, api_client):
        resp = api_client.put(
            "/api/inboxes/test@example.com/workflows/nope",
            json={
                "name": "nope",
                "match": {"intent": "x"},
                "action": {"type": "ignore"},
            },
        )
        assert resp.status_code == 404

    def test_delete_workflow(self, api_client):
        resp = api_client.delete("/api/inboxes/test@example.com/workflows/support")
        assert resp.status_code == 204

        resp2 = api_client.get("/api/inboxes/test@example.com/workflows")
        names = [w["name"] for w in resp2.json()]
        assert "support" not in names

    def test_delete_workflow_not_found(self, api_client):
        resp = api_client.delete("/api/inboxes/test@example.com/workflows/nope")
        assert resp.status_code == 404


class TestConfigPersistence:
    """Verify that mutations through the API are persisted to the YAML file."""

    def test_create_inbox_persists_to_yaml(self, api_client, api_config_path):
        api_client.post(
            "/api/inboxes",
            json={
                "address": "persisted@example.com",
                "password": "secret",
                "workflows": [
                    {
                        "name": "fallback",
                        "match": {"intent": "default"},
                        "action": {"type": "ignore"},
                    }
                ],
            },
        )

        raw = yaml.safe_load(api_config_path.read_text())
        addresses = [i["address"] for i in raw["inboxes"]]
        assert "persisted@example.com" in addresses

    def test_create_provider_persists_to_yaml(self, api_client, api_config_path):
        api_client.post(
            "/api/providers/new",
            json={"type": "anthropic", "model": "claude-3", "api_key": "sk-x"},
        )

        raw = yaml.safe_load(api_config_path.read_text())
        assert "new" in raw["providers"]
        assert raw["providers"]["new"]["type"] == "anthropic"

    def test_delete_inbox_persists_to_yaml(self, api_client, api_config_path):
        api_client.delete("/api/inboxes/test@example.com")

        raw = yaml.safe_load(api_config_path.read_text())
        assert len(raw["inboxes"]) == 0
