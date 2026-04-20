"""Strategy context engine - Disk-backed strategy memo storage."""

import json
import time
from pathlib import Path

import structlog

from synx_mt5.security.injection_shield import sanitise_string

log = structlog.get_logger(__name__)


class StrategyContextEngine:
    """Stores and retrieves trading strategy context memo."""

    def __init__(self, storage_path: Path):
        self._path = storage_path / "strategy_context.json"
        self._context = self._load()

    def _load(self) -> dict:
        """Load context from disk."""
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except json.JSONDecodeError:
                pass
        return {"context": "", "last_updated": None, "set_by": None}

    def _save(self) -> None:
        """Save context to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._context, indent=2))

    def set(self, context: str, agent_id: str = "unknown") -> None:
        """Set strategy context."""
        safe_context = sanitise_string(context, "strategy_context")
        self._context = {
            "context": safe_context[:2000],
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "set_by": agent_id,
        }
        self._save()
        log.info("strategy_context_updated", agent=agent_id)

    def get(self) -> dict:
        """Get current strategy context."""
        return self._context.copy()
