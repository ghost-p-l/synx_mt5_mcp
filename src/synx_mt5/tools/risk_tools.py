"""Risk & Audit Tools - Risk status, limits, and audit log operations."""

from contextlib import suppress as contextlib_suppress
from typing import Any

import structlog
from pydantic import BaseModel

from synx_mt5.audit.engine import AuditEngine
from synx_mt5.idempotency.engine import IdempotencyEngine
from synx_mt5.risk.circuit_breaker import DrawdownCircuitBreaker
from synx_mt5.risk.hitl import HITLGate

log = structlog.get_logger(__name__)


async def handle_get_risk_status(
    service: "RiskService",
    args: dict,
) -> dict[str, Any]:
    result = await service.get_risk_status()
    return result.model_dump()


async def handle_verify_audit_chain(
    service: "RiskService",
    args: dict,
) -> dict[str, Any]:
    result = service.verify_audit_chain()
    return result.model_dump()


async def handle_get_audit_summary(
    service: "RiskService",
    args: dict,
) -> dict[str, Any]:
    last_n = args.get("last_n", 50)
    event_filter = args.get("event_filter")
    result = service.get_audit_summary(last_n=last_n, event_filter=event_filter)
    return result.model_dump()


async def handle_get_risk_limits(
    service: "RiskService",
    args: dict,
) -> dict[str, Any]:
    result = service.get_risk_limits()
    return result.model_dump()


class RiskStatusOutput(BaseModel):
    """Output for get_risk_status tool."""

    circuit_breaker: str
    session_drawdown_pct: float
    daily_drawdown_pct: float
    max_drawdown_limit_pct: float
    current_positions: int
    max_positions_limit: int
    risk_per_trade_pct: float
    pending_hitl_approvals: int
    idempotency_cache_size: int


class RiskLimitsOutput(BaseModel):
    """Output for get_risk_limits tool."""

    require_sl: bool
    min_sl_pips: int
    min_rr_ratio: float
    max_risk_per_trade_pct: float
    max_total_exposure_pct: float
    max_positions_per_symbol: int
    max_total_positions: int
    max_session_drawdown_pct: float
    max_daily_drawdown_pct: float
    cooldown_seconds: int


class AuditSummaryOutput(BaseModel):
    """Output for get_audit_summary tool."""

    total_records: int
    chain_valid: bool
    records: list[dict[str, Any]]


class AuditVerifyOutput(BaseModel):
    """Output for verify_audit_chain tool."""

    valid: bool
    total_records: int
    broken_at_seq: int | None = None
    errors: list[str] = []


class RiskService:
    """
    Service layer for risk and audit operations.
    """

    def __init__(
        self,
        audit: AuditEngine,
        risk_config: dict,
        circuit_breaker: DrawdownCircuitBreaker | None,
        hitl: HITLGate | None,
        idempotency: IdempotencyEngine | None,
        bridge: Any,
    ):
        self.audit = audit
        self.risk_config = risk_config
        self.circuit_breaker = circuit_breaker
        self.hitl = hitl
        self.idempotency = idempotency
        self.bridge = bridge

    async def get_risk_status(self) -> RiskStatusOutput:
        """Inspect current state of all risk subsystems."""
        cb_state = "unknown"
        cb_session_dd = 0.0
        cb_daily_dd = 0.0
        cb_session_limit = self.risk_config.get("max_session_drawdown_pct", 3.0)
        cb_daily_limit = self.risk_config.get("max_daily_drawdown_pct", 5.0)

        if self.circuit_breaker:
            cb_state = self.circuit_breaker.state.value
            status = self.circuit_breaker.get_status()
            drawdowns = self.circuit_breaker.get_current_drawdowns()
            cb_session_dd = drawdowns.get("session_drawdown_pct", 0.0)
            cb_daily_dd = drawdowns.get("daily_drawdown_pct", 0.0)
            cb_session_limit = status.get("max_session_drawdown_pct", cb_session_limit)
            cb_daily_limit = status.get("max_daily_drawdown_pct", cb_daily_limit)

        hitl_pending = 0
        if self.hitl:
            pending = self.hitl.get_pending()
            hitl_pending = pending.get("count", 0)

        idempotency_size = 0
        if self.idempotency:
            stats = self.idempotency.get_stats()
            idempotency_size = stats.get("cache_size", 0)

        positions_count = 0
        with contextlib_suppress(Exception):
            positions_count = await self.bridge.positions_total()

        return RiskStatusOutput(
            circuit_breaker=cb_state,
            session_drawdown_pct=round(cb_session_dd, 2),
            daily_drawdown_pct=round(cb_daily_dd, 2),
            max_drawdown_limit_pct=round(cb_session_limit, 2),
            current_positions=positions_count,
            max_positions_limit=self.risk_config.get("max_total_positions", 10),
            risk_per_trade_pct=self.risk_config.get("max_risk_per_trade_pct", 1.0),
            pending_hitl_approvals=hitl_pending,
            idempotency_cache_size=idempotency_size,
        )

    def get_risk_limits(self) -> RiskLimitsOutput:
        """View all configured risk limits."""
        return RiskLimitsOutput(
            require_sl=self.risk_config.get("require_sl", True),
            min_sl_pips=self.risk_config.get("min_sl_pips", 5),
            min_rr_ratio=self.risk_config.get("min_rr_ratio", 1.0),
            max_risk_per_trade_pct=self.risk_config.get("max_risk_per_trade_pct", 1.0),
            max_total_exposure_pct=self.risk_config.get("max_total_exposure_pct", 10.0),
            max_positions_per_symbol=self.risk_config.get("max_positions_per_symbol", 3),
            max_total_positions=self.risk_config.get("max_total_positions", 10),
            max_session_drawdown_pct=self.risk_config.get("max_session_drawdown_pct", 3.0),
            max_daily_drawdown_pct=self.risk_config.get("max_daily_drawdown_pct", 5.0),
            cooldown_seconds=self.risk_config.get("cooldown_seconds", 3600),
        )

    def get_audit_summary(
        self,
        last_n: int = 50,
        event_filter: str | None = None,
    ) -> AuditSummaryOutput:
        """Get summary of recent audit log entries."""
        records = self.audit.get_records(last_n=last_n, event_filter=event_filter)

        for record in records:
            record.pop("prev_hash", None)
            record.pop("self_hash", None)

        verification = self.audit.verify_chain()

        return AuditSummaryOutput(
            total_records=verification.get("total_records", len(records)),
            chain_valid=verification.get("valid", False),
            records=records,
        )

    def verify_audit_chain(self) -> AuditVerifyOutput:
        """Cryptographically verify audit log integrity."""
        result = self.audit.verify_chain()

        return AuditVerifyOutput(
            valid=result.get("valid", False),
            total_records=result.get("total_records", 0),
            broken_at_seq=result.get("broken_at_seq"),
            errors=result.get("errors", []),
        )
