"""Prompt Injection Shield - Sanitizes untrusted external input."""

import re
import unicodedata
from typing import Any

INJECTION_PATTERNS = [
    r"(?i)ignore\s+(previous|prior|all|above)\s+instructions?",
    r"(?i)disregard\s+(previous|prior|all|above)",
    r"(?i)you\s+are\s+now\s+(a|an)",
    r"(?i)new\s+instructions?:",
    r"(?i)system\s*prompt:",
    r"(?i)\[system\]",
    r"(?i)\[assistant\]",
    r"(?i)\[user\]",
    r"(?i)(close|sell|buy)\s+all\s+positions",
    r"(?i)execute\s+(order|trade)",
    r"(?i)transfer\s+funds?",
]

_COMPILED_PATTERNS = [re.compile(p) for p in INJECTION_PATTERNS]

_CONTROL_CHARS_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f"
    r"\x80-\x9f"
    r"\u200b-\u200f"
    r"\u202a-\u202e"
    r"\ufeff]"
)

MAX_FIELD_LENGTH = 512


class InjectionShieldError(Exception):
    """Raised when injection pattern is detected."""

    def __init__(self, reason: str, field: str):
        self.reason = reason
        self.field = field
        super().__init__(f"Injection shield violation in field '{field}': {reason}")


InjectionShieldViolation = InjectionShieldError


def sanitise_string(value: str, field_name: str = "unknown") -> str:
    """Sanitise a single string value."""
    if not isinstance(value, str):
        return str(value)

    cleaned = _CONTROL_CHARS_RE.sub("", value)
    normalised = unicodedata.normalize("NFKC", cleaned)

    for pattern in _COMPILED_PATTERNS:
        if pattern.search(normalised):
            raise InjectionShieldError(
                reason=f"Pattern match: {pattern.pattern[:40]}", field=field_name
            )

    if len(normalised) > MAX_FIELD_LENGTH:
        normalised = normalised[:MAX_FIELD_LENGTH] + " [TRUNCATED]"

    return normalised


def sanitise_dict(data: dict[str, Any], path: str = "") -> dict[str, Any]:
    """Recursively sanitise all string values in a dict."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        field_path = f"{path}.{key}" if path else key
        if isinstance(value, str):
            result[key] = sanitise_string(value, field_path)
        elif isinstance(value, dict):
            result[key] = sanitise_dict(value, field_path)
        elif isinstance(value, list):
            result[key] = sanitise_list(value, field_path)
        else:
            result[key] = value
    return result


def sanitise_list(data: list[Any], path: str = "") -> list[Any]:
    """Recursively sanitise all string values in a list."""
    result: list[Any] = []
    for i, item in enumerate(data):
        field_path = f"{path}[{i}]"
        if isinstance(item, str):
            result.append(sanitise_string(item, field_path))
        elif isinstance(item, dict):
            result.append(sanitise_dict(item, field_path))
        elif isinstance(item, list):
            result.append(sanitise_list(item, field_path))
        else:
            result.append(item)
    return result
