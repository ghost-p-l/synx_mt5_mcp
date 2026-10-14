"""Credential vault CLI - non-interactive OS keyring management.

This module implements the commands documented in ``docs/SETUP.md``::

    python -m synx_mt5.security.vault set-credential mt5_login
    python -m synx_mt5.security.vault set-credential mt5_password
    python -m synx_mt5.security.vault set-credential mt5_server <broker-server>
    python -m synx_mt5.security.vault status
    python -m synx_mt5.security.vault wizard

Omitting the value prompts securely via :func:`getpass.getpass` so secrets
never land in shell history. Passing the value inline works too, but is
discouraged for passwords.

Exit codes: 0 = ok, 1 = usage error / credential missing, 2 = keyring
backend unavailable.
"""

from __future__ import annotations

import argparse
import getpass
import sys

import keyring
import keyring.errors

from synx_mt5.security.secrets import (
    SYNX_SERVICE,
    CredentialKey,
    credential_setup_wizard,
    load_credential,
    store_credential,
)

KNOWN_KEYS = (
    CredentialKey.LOGIN,
    CredentialKey.PASSWORD,
    CredentialKey.SERVER,
    CredentialKey.EA_APIKEY,
)


def _warn_unknown_key(key: str) -> None:
    if key not in KNOWN_KEYS:
        print(
            f"warning: '{key}' is not a standard key "
            f"({', '.join(KNOWN_KEYS)}); storing anyway.",
            file=sys.stderr,
        )


def _backend_error(action: str, exc: Exception) -> int:
    print(f"error: keyring backend failed during {action}: {exc}", file=sys.stderr)
    print(
        "hint: headless/container systems often have no OS keyring. "
        "Install one (e.g. gnome-keyring / KWallet) or use the "
        "SYNX_VAULT_* environment variables documented in docs/SETUP.md.",
        file=sys.stderr,
    )
    return 2


def cmd_set(args: argparse.Namespace) -> int:
    """Store a credential; prompt securely when no value is given."""
    _warn_unknown_key(args.key)
    value = args.value
    if not value:
        try:
            value = getpass.getpass(f"Value for '{args.key}' (input hidden): ")
        except (EOFError, KeyboardInterrupt):
            print("\naborted.", file=sys.stderr)
            return 1
    if not value:
        print("error: empty value, nothing stored.", file=sys.stderr)
        return 1
    try:
        store_credential(args.key, value)
    except keyring.errors.KeyringError as exc:
        return _backend_error("store", exc)
    print(f"Stored '{args.key}' in OS keyring (service '{SYNX_SERVICE}').")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    """Show whether a credential exists; print it only with --show."""
    try:
        cred = load_credential(args.key)
    except keyring.errors.KeyringError as exc:
        return _backend_error("load", exc)
    if cred is None:
        print(f"'{args.key}' is not set.", file=sys.stderr)
        return 1
    if args.show:
        print(cred.value)
    else:
        print(f"'{args.key}' is set (value hidden; use --show to display).")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Remove a credential from the OS keyring."""
    try:
        keyring.delete_password(SYNX_SERVICE, args.key)
    except keyring.errors.PasswordDeleteError:
        print(f"'{args.key}' was not set; nothing to delete.", file=sys.stderr)
        return 1
    except keyring.errors.KeyringError as exc:
        return _backend_error("delete", exc)
    print(f"Deleted '{args.key}' from OS keyring.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    """Report which standard credentials are set (values never printed)."""
    missing = []
    for key in KNOWN_KEYS:
        try:
            present = keyring.get_password(SYNX_SERVICE, key) is not None
        except keyring.errors.KeyringError as exc:
            return _backend_error("status check", exc)
        print(f"  [{'OK' if present else 'MISSING'}] {key}")
        if key in (CredentialKey.LOGIN, CredentialKey.PASSWORD, CredentialKey.SERVER) and not present:
            missing.append(key)
    if missing:
        print(
            "Missing required credentials: " + ", ".join(missing) + ". "
            "Run `python -m synx_mt5.security.vault wizard` to set them.",
            file=sys.stderr,
        )
        return 1
    print("All required credentials are set.")
    return 0


def cmd_wizard(_args: argparse.Namespace) -> int:
    """Interactive credential setup (same as `synx-mt5 setup`)."""
    try:
        credential_setup_wizard()
    except keyring.errors.KeyringError as exc:
        return _backend_error("wizard", exc)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m synx_mt5.security.vault",
        description="Manage SYNX-MT5 OS keyring credentials (service 'synx-mt5').",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_set = sub.add_parser("set-credential", help="Store a credential (prompts securely if VALUE omitted).")
    p_set.add_argument("key", help="Credential key, e.g. mt5_login, mt5_password, mt5_server.")
    p_set.add_argument("value", nargs="?", default=None, help="Value to store (discouraged: lands in shell history).")
    p_set.set_defaults(func=cmd_set)

    p_get = sub.add_parser("get-credential", help="Check a credential (prints value only with --show).")
    p_get.add_argument("key", help="Credential key.")
    p_get.add_argument("--show", action="store_true", help="Print the secret value (avoid on shared screens).")
    p_get.set_defaults(func=cmd_get)

    p_del = sub.add_parser("delete-credential", help="Remove a credential from the keyring.")
    p_del.add_argument("key", help="Credential key.")
    p_del.set_defaults(func=cmd_delete)

    p_status = sub.add_parser("status", help="Show which standard credentials are set (values never printed).")
    p_status.set_defaults(func=cmd_status)

    p_wiz = sub.add_parser("wizard", help="Interactive setup wizard (same as `synx-mt5 setup`).")
    p_wiz.set_defaults(func=cmd_wizard)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
