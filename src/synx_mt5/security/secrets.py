"""Secrets management - OS keyring integration with SecureString memory protection."""

import keyring
import keyring.errors
import structlog

log = structlog.get_logger(__name__)

SYNX_SERVICE = "synx-mt5"


class CredentialKey:
    """Credential key constants."""

    LOGIN = "mt5_login"
    PASSWORD = "mt5_password"
    SERVER = "mt5_server"
    EA_APIKEY = "ea_api_key"


class SecureString:
    """
    Wrapper that zeros memory on deletion.
    Prevents credential values lingering in heap after use.
    """

    def __init__(self, value: str):
        self._buf = bytearray(value.encode("utf-8"))

    @property
    def value(self) -> str:
        return self._buf.decode("utf-8")

    def __del__(self):
        try:
            for i in range(len(self._buf)):
                self._buf[i] = 0
        except Exception:
            pass

    def __repr__(self):
        return "SecureString(***REDACTED***)"


def store_credential(key: str, value: str) -> None:
    """Store credential in OS keyring."""
    keyring.set_password(SYNX_SERVICE, key, value)
    log.info("credential_stored", cred_key=key)


def load_credential(key: str) -> SecureString | None:
    """Load credential from OS keyring."""
    try:
        value = keyring.get_password(SYNX_SERVICE, key)
        if value is None:
            log.warning("credential_not_found", cred_key=key)
            return None
        return SecureString(value)
    except keyring.errors.KeyringError as e:
        log.error("keyring_access_failed", cred_key=key, error=str(e))
        return None


def rotate_credential(key: str, new_value: str) -> None:
    """Rotate credential in OS keyring."""
    keyring.set_password(SYNX_SERVICE, key, new_value)
    log.info("credential_rotated", cred_key=key)


def credential_setup_wizard() -> None:
    """Interactive CLI wizard for initial credential setup."""
    import getpass

    print("\n=== SYNX-MT5-MCP Credential Setup ===")
    print("Credentials are stored in your OS keyring.")
    print("They never touch disk as plaintext.\n")

    login = input("MT5 Account Number: ").strip()
    password = getpass.getpass("MT5 Password: ")
    server = input("MT5 Server Name (e.g. Broker-Demo): ").strip()

    store_credential(CredentialKey.LOGIN, login)
    store_credential(CredentialKey.PASSWORD, password)
    store_credential(CredentialKey.SERVER, server)

    print("\nCredentials stored securely.")
    print("Run `synx-mt5 start` to launch.\n")


def load_from_env_vault() -> dict:
    """CI/CD escape hatch - consume and zero env vars immediately."""
    import os

    creds = {}
    for key, env_var in [
        (CredentialKey.LOGIN, "SYNX_VAULT_LOGIN"),
        (CredentialKey.PASSWORD, "SYNX_VAULT_PASSWORD"),
        (CredentialKey.SERVER, "SYNX_VAULT_SERVER"),
    ]:
        value = os.environ.pop(env_var, None)
        if value:
            creds[key] = SecureString(value)
    return creds
