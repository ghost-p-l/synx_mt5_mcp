"""Drawdown circuit breaker - Auto-suspends trading when drawdown exceeds limit."""

import asyncio
import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import structlog

from synx_mt5.audit import AuditEngine, AuditEventType

log = structlog.get_logger(__name__)


class BreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class DrawdownCircuitBreaker:
    """Monitors drawdown and trips circuit breaker when limit exceeded."""

    def __init__(self, config: dict, bridge, audit: AuditEngine, storage_path: Path | None = None):
        self.max_session_drawdown_pct = config.get("max_session_drawdown_pct", 5.0)  # 5% session max
        self.max_daily_drawdown_pct = config.get("max_daily_drawdown_pct", 10.0)  # 10% daily max
        self.cooldown_seconds = config.get("cooldown_seconds", 60)  # 60s between trades
        self._state = BreakerState.CLOSED
        self._session_high_equity: float | None = None
        self._daily_high_equity: float | None = None
        self._daily_date: str | None = None
        self._current_equity: float = 0.0
        self._bridge = bridge
        self._audit = audit
        self._monitoring = False
        self._state_file = (
            storage_path or Path("~/.synx-mt5")
        ).expanduser() / "circuit_breaker_state.json"
        self._load_state()

    def _load_state(self) -> None:
        """Load state from file if exists."""
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                self._state = BreakerState(data.get("state", "closed"))
            except Exception:
                pass

    def _save_state(self) -> None:
        """Save state to file."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps({"state": self._state.value}))

    @property
    def state(self) -> BreakerState:
        """Get current breaker state."""
        return self._state

    @state.setter
    def state(self, value: BreakerState) -> None:
        """Set breaker state (for testing)."""
        self._state = value
        self._save_state()

    async def start_monitoring(self):
        """Start drawdown monitoring loop."""
        self._monitoring = True
        asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self):
        """Stop drawdown monitoring."""
        self._monitoring = False

    async def _monitor_loop(self):
        """Monitor equity and check drawdown."""
        while self._monitoring:
            await asyncio.sleep(10)
            try:
                account = await self._bridge.account_info()
                equity = account.get("equity", 0)
                self._current_equity = equity
                current_date = datetime.now(UTC).strftime("%Y-%m-%d")

                if self._session_high_equity is None:
                    self._session_high_equity = equity
                self._session_high_equity = max(self._session_high_equity, equity)

                session_dd_pct = 0.0
                if self._session_high_equity > 0:
                    session_dd_pct = (
                        (self._session_high_equity - equity) / self._session_high_equity * 100
                    )

                if (
                    session_dd_pct >= self.max_session_drawdown_pct
                    and self.state == BreakerState.CLOSED
                ):
                    await self._trip_breaker(session_dd_pct, equity, "session")
                    continue

                if self._daily_high_equity is None or self._daily_date != current_date:
                    self._daily_high_equity = equity
                    self._daily_date = current_date

                self._daily_high_equity = max(self._daily_high_equity, equity)

                daily_dd_pct = 0.0
                if self._daily_high_equity > 0:
                    daily_dd_pct = (
                        (self._daily_high_equity - equity) / self._daily_high_equity * 100
                    )

                if (
                    daily_dd_pct >= self.max_daily_drawdown_pct
                    and self.state == BreakerState.CLOSED
                ):
                    await self._trip_breaker(daily_dd_pct, equity, "daily")

            except Exception as e:
                log.error("circuit_breaker_monitor_error", error=str(e))

    async def _trip_breaker(
        self, drawdown_pct: float, equity: float, drawdown_type: str = "session"
    ):
        """Trip the circuit breaker open."""
        self._state = BreakerState.OPEN
        self._save_state()
        self._audit.log(
            AuditEventType.RISK_CIRCUIT_BREAKER_OPEN,
            {
                "drawdown_type": drawdown_type,
                "drawdown_pct": drawdown_pct,
                "equity": equity,
                "limit_pct": self.max_session_drawdown_pct
                if drawdown_type == "session"
                else self.max_daily_drawdown_pct,
            },
        )
        log.warning(
            "circuit_breaker_tripped",
            drawdown_type=drawdown_type,
            drawdown=drawdown_pct,
            limit=self.max_session_drawdown_pct
            if drawdown_type == "session"
            else self.max_daily_drawdown_pct,
        )
        asyncio.create_task(self._cooldown())

    async def _cooldown(self):
        """Cooldown period before allowing half-open state."""
        await asyncio.sleep(self.cooldown_seconds)
        self._state = BreakerState.HALF_OPEN
        self._save_state()
        log.info("circuit_breaker_half_open")

    def assert_closed(self) -> None:
        """Assert breaker is closed, raise if open."""
        if self.state == BreakerState.OPEN:
            raise RuntimeError(
                f"Execution suspended: circuit breaker OPEN. "
                f"Drawdown limit ({self.max_session_drawdown_pct}%) exceeded. "
                f"Cooldown: {self.cooldown_seconds}s. "
                f"Manual reset: synx-mt5 risk reset-breaker"
            )
        if self.state == BreakerState.HALF_OPEN:
            raise RuntimeError(
                "Circuit breaker in HALF_OPEN state. Waiting for cooldown completion."
            )

    def reset(self) -> None:
        """Manually reset circuit breaker."""
        self._state = BreakerState.CLOSED
        self._session_high_equity = None
        self._daily_high_equity = None
        self._daily_date = None
        self._current_equity = 0.0
        self._save_state()
        self._audit.log(
            AuditEventType.RISK_CIRCUIT_BREAKER_RESET,
            {"reset_by": "cli"},
        )
        log.info("circuit_breaker_reset")

    def get_status(self) -> dict:
        """Get current breaker status."""
        return {
            "state": self.state.value,
            "max_session_drawdown_pct": self.max_session_drawdown_pct,
            "max_daily_drawdown_pct": self.max_daily_drawdown_pct,
            "cooldown_seconds": self.cooldown_seconds,
        }

    def get_current_drawdowns(self) -> dict:
        """Get current session and daily drawdown percentages."""
        return {
            "session_drawdown_pct": self._get_session_drawdown_pct(),
            "daily_drawdown_pct": self._get_daily_drawdown_pct(),
            "session_high_equity": self._session_high_equity,
            "daily_high_equity": self._daily_high_equity,
        }

    def _get_session_drawdown_pct(self) -> float:
        """Calculate current session drawdown percentage."""
        if self._session_high_equity is None or self._session_high_equity <= 0:
            return 0.0
        return max(
            0.0,
            (self._session_high_equity - self._current_equity) / self._session_high_equity * 100,
        )

    def _get_daily_drawdown_pct(self) -> float:
        """Calculate current daily drawdown percentage."""
        if self._daily_high_equity is None or self._daily_high_equity <= 0:
            return 0.0
        return max(
            0.0, (self._daily_high_equity - self._current_equity) / self._daily_high_equity * 100
        )
