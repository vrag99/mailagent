import pytest

from mailagent.api.auth import create_api_key, list_api_keys, revoke_api_key


class TestApiKeyManagement:
    def test_create_key(self, tmp_path):
        path = str(tmp_path / "keys.yml")
        key = create_api_key(api_keys_path=path, name="test-key")
        assert key.startswith("ma_")
        assert len(key) > 10

    def test_list_keys(self, tmp_path):
        path = str(tmp_path / "keys.yml")
        create_api_key(api_keys_path=path, name="key1")
        create_api_key(api_keys_path=path, name="key2")
        keys = list_api_keys(api_keys_path=path)
        assert len(keys) == 2
        names = {k["name"] for k in keys}
        assert names == {"key1", "key2"}

    def test_list_keys_empty(self, tmp_path):
        path = str(tmp_path / "keys.yml")
        keys = list_api_keys(api_keys_path=path)
        assert keys == []

    def test_revoke_key(self, tmp_path):
        path = str(tmp_path / "keys.yml")
        create_api_key(api_keys_path=path, name="to-revoke")
        keys = list_api_keys(api_keys_path=path)
        assert len(keys) == 1

        prefix = keys[0]["hash_prefix"]
        assert revoke_api_key(prefix, api_keys_path=path) is True
        assert list_api_keys(api_keys_path=path) == []

    def test_revoke_key_not_found(self, tmp_path):
        path = str(tmp_path / "keys.yml")
        assert revoke_api_key("nonexistent", api_keys_path=path) is False

    def test_key_uniqueness(self, tmp_path):
        path = str(tmp_path / "keys.yml")
        k1 = create_api_key(api_keys_path=path, name="a")
        k2 = create_api_key(api_keys_path=path, name="b")
        assert k1 != k2
