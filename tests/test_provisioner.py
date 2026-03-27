import pytest

from mailagent.provisioner import Provisioner


@pytest.fixture
def provisioner(tmp_path):
    return Provisioner(str(tmp_path))


class TestProvisioner:
    def test_available(self, provisioner):
        assert provisioner.available is True

    def test_not_available(self):
        p = Provisioner("/nonexistent/path")
        assert p.available is False

    def test_add_account(self, provisioner, tmp_path):
        provisioner.add_account("user@example.com", "password123")
        content = (tmp_path / "postfix-accounts.cf").read_text()
        assert "user@example.com|{SHA512-CRYPT}" in content

    def test_add_account_idempotent(self, provisioner, tmp_path):
        provisioner.add_account("user@example.com", "pw1")
        provisioner.add_account("user@example.com", "pw2")
        content = (tmp_path / "postfix-accounts.cf").read_text()
        # Should only appear once
        assert content.count("user@example.com|") == 1

    def test_list_accounts(self, provisioner):
        provisioner.add_account("a@example.com", "pw")
        provisioner.add_account("b@example.com", "pw")
        accounts = provisioner.list_accounts()
        assert sorted(accounts) == ["a@example.com", "b@example.com"]

    def test_list_accounts_empty(self, provisioner):
        assert provisioner.list_accounts() == []

    def test_remove_account(self, provisioner, tmp_path):
        provisioner.add_account("a@example.com", "pw")
        provisioner.add_account("b@example.com", "pw")
        provisioner.remove_account("a@example.com")
        accounts = provisioner.list_accounts()
        assert accounts == ["b@example.com"]

    def test_remove_account_nonexistent(self, provisioner):
        # Should not raise
        provisioner.remove_account("missing@example.com")

    def test_account_exists_check(self, provisioner):
        assert provisioner._account_exists("user@example.com") is False
        provisioner.add_account("user@example.com", "pw")
        assert provisioner._account_exists("user@example.com") is True
