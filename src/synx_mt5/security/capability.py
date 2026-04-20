"""Capability Profile Guard - Enforces tool access based on profiles."""

from collections.abc import Callable
from functools import wraps

from synx_mt5.audit import AuditEngine, AuditEventType

_ACTIVE_PROFILE: set[str] = set()
_ACTIVE_PROFILE_NAME: str = ""
_AUDIT_ENGINE: AuditEngine | None = None


def init_audit(audit_engine: AuditEngine) -> None:
    """Set the audit engine reference (called by server on startup)."""
    global _AUDIT_ENGINE
    _AUDIT_ENGINE = audit_engine


EXECUTION_TOOLS = frozenset(
    [
        "order_send",
        "order_modify",
        "order_cancel",
        "position_close",
        "position_close_all",
        "position_modify",
    ]
)

READ_ONLY_EXCLUDES = frozenset(
    [
        "order_send",
        "order_modify",
        "order_cancel",
        "position_close",
        "position_close_all",
        "position_modify",
    ]
)


def load_profile(profile_name: str, allowed_tools: list[str]) -> None:
    """Load capability profile."""
    global _ACTIVE_PROFILE, _ACTIVE_PROFILE_NAME
    if profile_name == "read_only":
        filtered = [t for t in allowed_tools if t not in READ_ONLY_EXCLUDES]
    else:
        filtered = allowed_tools
    _ACTIVE_PROFILE = set(filtered)
    _ACTIVE_PROFILE_NAME = profile_name
    if _AUDIT_ENGINE is not None:
        _AUDIT_ENGINE.log(
            AuditEventType.SECURITY_PROFILE_LOADED,
            {
                "profile": profile_name,
                "tool_count": len(_ACTIVE_PROFILE),
            },
        )


def get_active_profile() -> tuple[str, set[str]]:
    """Get current active profile name and tools."""
    return _ACTIVE_PROFILE_NAME, _ACTIVE_PROFILE


def reset_profile() -> None:
    """Reset active profile. For testing use only."""
    global _ACTIVE_PROFILE, _ACTIVE_PROFILE_NAME
    _ACTIVE_PROFILE.clear()
    _ACTIVE_PROFILE_NAME = ""


def require_capability(tool_name: str) -> Callable:
    """
    Decorator to enforce capability profile on tool functions.

    Usage:
        @require_capability("order_send")
        async def order_send_tool(self, args):
            ...
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            if tool_name not in _ACTIVE_PROFILE:
                if _AUDIT_ENGINE is not None:
                    _AUDIT_ENGINE.log(
                        AuditEventType.SECURITY_CAPABILITY_DENIED,
                        {
                            "tool": tool_name,
                            "profile": _ACTIVE_PROFILE_NAME,
                            "profile_tools": list(_ACTIVE_PROFILE),
                        },
                    )
                raise PermissionError(
                    f"Tool '{tool_name}' is not available in the active "
                    f"capability profile ('{_ACTIVE_PROFILE_NAME}'). "
                    f"To enable it, update your synx.yaml profile setting."
                )
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def is_tool_allowed(tool_name: str) -> bool:
    """Check if tool is allowed in current profile."""
    return tool_name in _ACTIVE_PROFILE
