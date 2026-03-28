from pathlib import Path

from mailagent.provisioner import Provisioner


def test_add_account(tmp_path):
    p = Provisioner(str(tmp_path))
    p.add_account("user@example.com", "secret")

    accounts_file = tmp_path / "postfix-accounts.cf"
    assert accounts_file.exists()

    content = accounts_file.read_text()
    assert content.startswith("user@example.com|{SHA512-CRYPT}$6")


def test_add_duplicate_account_is_idempotent(tmp_path):
    p = Provisioner(str(tmp_path))
    # Create the accounts file first
    (tmp_path / "postfix-accounts.cf").write_text("")
    p.add_account("user@example.com", "secret")
    p.add_account("user@example.com", "secret")

    content = (tmp_path / "postfix-accounts.cf").read_text()
    lines = [l for l in content.strip().splitlines() if l.startswith("user@example.com|")]
    assert len(lines) == 1


def test_remove_account(tmp_path):
    p = Provisioner(str(tmp_path))
    p.add_account("a@example.com", "pass1")
    p.add_account("b@example.com", "pass2")

    p.remove_account("a@example.com")

    content = (tmp_path / "postfix-accounts.cf").read_text()
    assert "a@example.com" not in content
    assert "b@example.com" in content


def test_list_accounts(tmp_path):
    p = Provisioner(str(tmp_path))
    p.add_account("a@example.com", "pass1")
    p.add_account("b@example.com", "pass2")

    accounts = p.list_accounts()
    assert set(accounts) == {"a@example.com", "b@example.com"}


def test_list_accounts_empty(tmp_path):
    p = Provisioner(str(tmp_path))
    assert p.list_accounts() == []


def test_available(tmp_path):
    p = Provisioner(str(tmp_path))
    assert p.available is True

    p2 = Provisioner(str(tmp_path / "nonexistent"))
    assert p2.available is False


def test_remove_nonexistent_is_noop(tmp_path):
    p = Provisioner(str(tmp_path))
    # Should not raise
    p.remove_account("ghost@example.com")
