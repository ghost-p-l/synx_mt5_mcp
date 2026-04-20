"""Agent memory system - Disk-backed key-value store for agent state."""

import json
import time
from pathlib import Path

import structlog

from synx_mt5.security.injection_shield import sanitise_dict, sanitise_string

log = structlog.get_logger(__name__)


class AgentMemory:
    """Persistent key-value store for agent memory."""

    RESERVED_PREFIX = "system_"
    MAX_VALUE_SIZE = 65536

    def __init__(self, storage_path: Path):
        self._path = storage_path / "agent_memory.json"
        self._store = self._load()

    def _load(self) -> dict:
        """Load memory from disk."""
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except json.JSONDecodeError:
                pass
        return {}

    def _save(self) -> None:
        """Save memory to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._store, indent=2, default=str))

    def set(self, key: str, value) -> None:
        """Store a value."""
        if not key.replace("_", "").isalnum():
            raise ValueError("Memory keys must be alphanumeric with underscores only")
        if key.startswith(self.RESERVED_PREFIX):
            raise ValueError(f"Key prefix '{self.RESERVED_PREFIX}' is reserved")

        serialised = json.dumps(value, default=str)
        if len(serialised) > self.MAX_VALUE_SIZE:
            raise ValueError(f"Value exceeds max size {self.MAX_VALUE_SIZE} bytes")

        if isinstance(value, str):
            value = sanitise_string(value, f"memory:{key}")
        elif isinstance(value, dict):
            value = sanitise_dict(value, f"memory:{key}")

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        existing = self._store.get(key, {})
        self._store[key] = {
            "value": value,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }
        self._save()
        log.info("memory_stored", key=key, size=len(serialised))

    def get(self, key: str) -> dict:
        """Retrieve a value."""
        if key not in self._store:
            return {"key": key, "value": None, "created_at": None, "updated_at": None}
        return {"key": key, **self._store[key]}

    def list_keys(self) -> list[str]:
        """List all memory keys."""
        return list(self._store.keys())

    def delete(self, key: str) -> bool:
        """Delete a key."""
        if key in self._store:
            del self._store[key]
            self._save()
            return True
        return False
