"""Unit tests for the credential vault CLI (synx_mt5.security.vault).

Keyring is fully mocked: no test touches the real OS keyring.
"""

from unittest.mock import patch

import keyring.errors
import pytest

from synx_mt5.security import vault
from synx_mt5.security.secrets import SecureString


def run(*argv):
    return vault.main(list(argv))


def test_set_with_inline_value(capsys):
    with patch.object(vault, "store_credential") as store:
        assert run("set-credential", "mt5_login", "12345") == 0
    store.assert_called_once_with("mt5_login", "12345")
    assert "Stored 'mt5_login'" in capsys.readouterr().out


def test_set_prompts_securely_when_value_omitted(capsys):
    with patch.object(vault, "store_credential") as store, patch.object(
        vault.getpass, "getpass", return_value="s3cret"
    ) as prompt:
        assert run("set-credential", "mt5_password") == 0
    prompt.assert_called_once()
    store.assert_called_once_with("mt5_password", "s3cret")


def test_set_empty_value_rejected(capsys):
    with patch.object(vault.getpass, "getpass", return_value=""):
        assert run("set-credential", "mt5_login") == 1
    assert "empty value" in capsys.readouterr().err


def test_set_unknown_key_warns_but_stores(capsys):
    with patch.object(vault, "store_credential") as store:
        assert run("set-credential", "some_custom_key", "v") == 0
    store.assert_called_once_with("some_custom_key", "v")
    assert "not a standard key" in capsys.readouterr().err


def test_set_backend_failure_exit_2(capsys):
    with patch.object(
        vault, "store_credential", side_effect=keyring.errors.KeyringError("no backend")
    ):
        assert run("set-credential", "mt5_login", "x") == 2
    assert "keyring backend failed" in capsys.readouterr().err


def test_get_hides_value_by_default(capsys):
    with patch.object(vault, "load_credential", return_value=SecureString("s3cret")):
        assert run("get-credential", "mt5_password") == 0
    out = capsys.readouterr().out
    assert "is set" in out
    assert "s3cret" not in out


def test_get_show_prints_value(capsys):
    with patch.object(vault, "load_credential", return_value=SecureString("s3cret")):
        assert run("get-credential", "mt5_password", "--show") == 0
    assert "s3cret" in capsys.readouterr().out


def test_get_missing_key_exit_1(capsys):
    with patch.object(vault, "load_credential", return_value=None):
        assert run("get-credential", "mt5_server") == 1
    assert "not set" in capsys.readouterr().err


def test_delete_existing(capsys):
    with patch("keyring.delete_password") as delete:
        assert run("delete-credential", "mt5_server") == 0
    delete.assert_called_once_with("synx-mt5", "mt5_server")
    assert "Deleted" in capsys.readouterr().out


def test_delete_missing_exit_1(capsys):
    with patch(
        "keyring.delete_password",
        side_effect=keyring.errors.PasswordDeleteError("gone"),
    ):
        assert run("delete-credential", "mt5_server") == 1


def test_status_all_set(capsys):
    with patch("keyring.get_password", return_value="x"):
        assert run("status") == 0
    assert "All required credentials are set." in capsys.readouterr().out


def test_status_missing_required_exit_1(capsys):
    def fake_get(service, key):
        return "x" if key == "mt5_login" else None

    with patch("keyring.get_password", side_effect=fake_get):
        assert run("status") == 1
    out = capsys.readouterr()
    assert "[OK] mt5_login" in out.out
    assert "[MISSING] mt5_password" in out.out


def test_wizard_delegates():
    with patch.object(vault, "credential_setup_wizard") as wiz:
        assert run("wizard") == 0
    wiz.assert_called_once_with()


def test_no_command_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        run()
    assert exc.value.code == 2
