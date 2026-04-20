"""Audit Engine - Tamper-evident append-only logging with cryptographic chain."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import structlog

log = structlog.get_logger(__name__)


class VerifyResult(TypedDict):
    valid: bool
    total_records: int
    broken_at_seq: int | None
    errors: list[str]


class AuditEventType:
    """Audit event type constants."""

    SERVER_START = "server.start"
    SERVER_STOP = "server.stop"
    CREDENTIAL_LOAD = "credential.load"
    CREDENTIAL_ROTATE = "credential.rotate"
    TOOL_INVOCATION = "tool.invocation"
    SECURITY_INJECTION_BLOCKED = "security.injection_blocked"
    SECURITY_CAPABILITY_DENIED = "security.capability_denied"
    SECURITY_PROFILE_LOADED = "security.profile_loaded"
    RISK_PREFLIGHT_PASSED = "risk.preflight_passed"
    RISK_PREFLIGHT_FAILED = "risk.preflight_failed"
    RISK_CIRCUIT_BREAKER_OPEN = "risk.circuit_breaker_open"
    RISK_CIRCUIT_BREAKER_RESET = "risk.circuit_breaker_reset"
    RISK_HITL_REQUIRED = "risk.hitl_required"
    RISK_HITL_APPROVED = "risk.hitl_approved"
    RISK_HITL_REJECTED = "risk.hitl_rejected"
    IDEMPOTENCY_DUPLICATE_BLOCKED = "idempotency.duplicate_blocked"
    BRIDGE_CONNECT = "bridge.connect"
    BRIDGE_DISCONNECT = "bridge.disconnect"
    BRIDGE_RECONNECT = "bridge.reconnect"
    MQL5_COMPILE_SUCCESS = "mql5.compile_success"
    MQL5_COMPILE_ERROR = "mql5.compile_error"
    CHART_OPERATION = "chart.operation"


ALL_EVENT_TYPES = {
    v for k, v in AuditEventType.__dict__.items() if k.isupper() and isinstance(v, str)
}


class AuditEngine:
    """
    Append-only audit log with SHA-256 hash chain.
    Tampering with any record invalidates all subsequent entries.
    """

    def __init__(
        self,
        log_path: Path,
        chain_verification: bool = True,
        rotate_size_mb: int = 100,
    ):
        self.log_path = log_path
        self.chain_verification = chain_verification
        self.rotate_size_mb = rotate_size_mb
        self._seq = 0
        self._last_hash = "genesis"
        self._session_id = self._generate_session_id()
        self._ensure_log_exists()
        self._load_last_hash()

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import secrets

        return f"ses_{secrets.token_hex(4)}"

    def _ensure_log_exists(self) -> None:
        """Ensure log directory and file exist."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch()

    def _load_last_hash(self) -> None:
        """Load the last hash from existing log for chain continuation."""
        if self.log_path.stat().st_size == 0:
            return
        try:
            with open(self.log_path) as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        self._seq = record.get("seq", self._seq)
                        self._last_hash = record.get("self_hash", self._last_hash)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("audit_chain_load_failed", error=str(e))

    def _compute_hash(self, data: dict) -> str:
        """Compute SHA-256 hash of record data (excluding hash chain fields)."""
        hashable = {k: v for k, v in data.items() if k not in ("prev_hash", "self_hash")}
        content = json.dumps(hashable, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

    def _should_rotate(self) -> bool:
        """Check if log should be rotated based on size."""
        if self.log_path.stat().st_size == 0:
            return False
        size_mb = self.log_path.stat().st_size / (1024 * 1024)
        return size_mb >= self.rotate_size_mb

    def _rotate_log(self) -> None:
        """Rotate audit log when size limit reached."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        rotated_path = self.log_path.with_suffix(f".{timestamp}.jsonl")
        self.log_path.rename(rotated_path)
        self._ensure_log_exists()
        self._last_hash = "genesis"
        self._seq = 0
        log.info("audit_log_rotated", new_path=str(rotated_path))

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        return self._session_id

    def log(self, event_type: str, data: dict | None = None) -> dict:
        """
        Write an audit record to the log.

        Args:
            event_type: Type of event (see AuditEventType)
            data: Additional event data

        Returns:
            The audit record that was written
        """
        if self._should_rotate():
            self._rotate_log()

        self._seq += 1
        now = datetime.now(UTC).isoformat()

        record = {
            "seq": self._seq,
            "ts": now,
            "event": event_type,
            "session_id": self._session_id,
            "prev_hash": self._last_hash,
            **(data or {}),
        }

        record["self_hash"] = self._compute_hash(record)
        self._last_hash = record["self_hash"]

        with open(self.log_path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")

        log.debug("audit_logged", event_type=event_type, seq=self._seq)
        return record

    def get_records(
        self,
        last_n: int | None = None,
        event_filter: str | None = None,
    ) -> list[dict]:
        """
        Read audit records from the log.

        Args:
            last_n: Return only last N records
            event_filter: Filter by event type (substring match)

        Returns:
            List of audit records
        """
        if not self.log_path.exists():
            return []

        records = []
        try:
            with open(self.log_path) as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        if event_filter and event_filter not in record.get("event", ""):
                            continue
                        records.append(record)
        except json.JSONDecodeError as e:
            log.error("audit_log_read_failed", error=str(e))

        if last_n:
            records = records[-last_n:]
        return records

    def verify_chain(self) -> VerifyResult:
        """
        Verify the integrity of the audit log chain.

        Returns:
            Verification result with valid flag and broken_at seq if invalid
        """
        result: VerifyResult = {
            "valid": True,
            "total_records": 0,
            "broken_at_seq": None,
            "errors": [],
        }

        if not self.log_path.exists():
            return result

        expected_prev_hash = "genesis"
        seq = 0

        try:
            with open(self.log_path) as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        seq = record.get("seq", seq)
                        prev_hash = record.get("prev_hash", "")
                        self_hash = record.get("self_hash", "")

                        if prev_hash != expected_prev_hash:
                            result["valid"] = False
                            result["broken_at_seq"] = seq
                            result["errors"].append(
                                f"Seq {seq}: prev_hash mismatch "
                                f"(expected {expected_prev_hash}, got {prev_hash})"
                            )
                            break

                        computed_hash = self._compute_hash(record)
                        if computed_hash != self_hash:
                            result["valid"] = False
                            result["broken_at_seq"] = seq
                            result["errors"].append(
                                f"Seq {seq}: self_hash mismatch "
                                f"(expected {computed_hash}, got {self_hash})"
                            )
                            break

                        expected_prev_hash = self_hash
                        result["total_records"] += 1

        except (OSError, json.JSONDecodeError) as e:
            result["valid"] = False
            result["errors"].append(f"Read error: {str(e)}")

        return result
