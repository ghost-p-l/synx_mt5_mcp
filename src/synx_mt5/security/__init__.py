"""Security module - Secrets management, injection shield, capability profiles."""

from synx_mt5.security.capability import (
    get_active_profile,
    init_audit,
    is_tool_allowed,
    load_profile,
    require_capability,
)
from synx_mt5.security.injection_shield import (
    InjectionShieldViolation,
    sanitise_dict,
    sanitise_list,
    sanitise_string,
)
from synx_mt5.security.rate_limiter import RateLimiter, SlidingWindowCounter
from synx_mt5.security.secrets import (
    CredentialKey,
    SecureString,
    credential_setup_wizard,
    load_credential,
    load_from_env_vault,
    rotate_credential,
    store_credential,
)
from synx_mt5.security.tool_validator import ToolSchemaIntegrity, ToolValidator

__all__ = [
    "CredentialKey",
    "SecureString",
    "store_credential",
    "load_credential",
    "rotate_credential",
    "credential_setup_wizard",
    "load_from_env_vault",
    "InjectionShieldViolation",
    "sanitise_string",
    "sanitise_dict",
    "sanitise_list",
    "init_audit",
    "load_profile",
    "require_capability",
    "get_active_profile",
    "is_tool_allowed",
    "RateLimiter",
    "SlidingWindowCounter",
    "ToolSchemaIntegrity",
    "ToolValidator",
]
