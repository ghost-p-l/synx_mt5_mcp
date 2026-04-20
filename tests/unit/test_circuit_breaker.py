"""Unit tests for circuit breaker module."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from synx_mt5.audit.engine import AuditEngine
from synx_mt5.risk.circuit_breaker import BreakerState, DrawdownCircuitBreaker


class TestBreakerState:
    """Test BreakerState enum."""

    def test_breaker_state_values(self):
        """Test enum values."""
        assert BreakerState.CLOSED.value == "closed"
        assert BreakerState.OPEN.value == "open"
        assert BreakerState.HALF_OPEN.value == "half_open"


class TestDrawdownCircuitBreaker:
    """Test DrawdownCircuitBreaker class."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = MagicMock()
        bridge.account_info = AsyncMock(return_value={"equity": 10000})
        return bridge

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory that persists for the test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def _make_breaker(self, temp_dir, config=None, bridge=None):
        """Helper to create breaker with audit log in temp_dir."""
        config = config or {}
        bridge = bridge or MagicMock()
        audit = AuditEngine(Path(temp_dir) / "audit.jsonl")
        storage = Path(temp_dir) / "state.json"
        return DrawdownCircuitBreaker(
            config=config, bridge=bridge, audit=audit, storage_path=storage
        )

    def test_init_default_values(self, temp_dir, mock_bridge):
        """Test init with default values."""
        breaker = self._make_breaker(temp_dir, config={}, bridge=mock_bridge)
        assert breaker.max_session_drawdown_pct == 5.0
        assert breaker.max_daily_drawdown_pct == 10.0
        assert breaker.cooldown_seconds == 60
        assert breaker.state == BreakerState.CLOSED

    def test_init_custom_values(self, temp_dir, mock_bridge):
        """Test init with custom values."""
        config = {
            "max_session_drawdown_pct": 5.0,
            "max_daily_drawdown_pct": 10.0,
            "cooldown_seconds": 1800,
        }
        breaker = self._make_breaker(temp_dir, config=config, bridge=mock_bridge)
        assert breaker.max_session_drawdown_pct == 5.0
        assert breaker.max_daily_drawdown_pct == 10.0
        assert breaker.cooldown_seconds == 1800

    def test_initial_state_closed(self, temp_dir, mock_bridge):
        """Test initial state is CLOSED."""
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge)
        assert breaker.state == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_start_monitoring(self, temp_dir, mock_bridge):
        """Test start monitoring sets flag."""
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge)
        await breaker.start_monitoring()
        assert breaker._monitoring is True
        await breaker.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, temp_dir, mock_bridge):
        """Test stop monitoring clears flag."""
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge)
        await breaker.start_monitoring()
        await breaker.stop_monitoring()
        assert breaker._monitoring is False

    @pytest.mark.asyncio
    async def test_trip_breaker_changes_state(self, temp_dir, mock_bridge):
        """Test _trip_breaker changes state to OPEN."""
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge)
        await breaker._trip_breaker(5.0, 9500)
        assert breaker.state == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_trip_breaker_logs_audit(self, temp_dir, mock_bridge):
        """Test _trip_breaker logs to audit."""
        audit = AuditEngine(Path(temp_dir) / "audit.jsonl")
        storage = Path(temp_dir) / "state.json"
        breaker = DrawdownCircuitBreaker(
            config={}, bridge=mock_bridge, audit=audit, storage_path=storage
        )
        await breaker._trip_breaker(5.0, 9500)
        records = audit.get_records()
        assert len(records) == 1
        assert records[0]["event"] == "risk.circuit_breaker_open"

    @pytest.mark.asyncio
    async def test_cooldown_transitions_to_half_open(self, temp_dir, mock_bridge):
        """Test cooldown transitions state to HALF_OPEN."""
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge, config={"cooldown_seconds": 0})
        breaker._state = BreakerState.OPEN
        await breaker._cooldown()
        await asyncio.sleep(0.05)
        assert breaker.state == BreakerState.HALF_OPEN

    def test_assert_closed_raises_when_open(self, temp_dir, mock_bridge):
        """Test assert_closed raises RuntimeError when OPEN."""
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge)
        breaker._state = BreakerState.OPEN
        with pytest.raises(RuntimeError) as exc_info:
            breaker.assert_closed()
        assert "circuit breaker OPEN" in str(exc_info.value)

    def test_assert_closed_raises_when_half_open(self, temp_dir, mock_bridge):
        """Test assert_closed raises RuntimeError when HALF_OPEN."""
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge)
        breaker._state = BreakerState.HALF_OPEN
        with pytest.raises(RuntimeError) as exc_info:
            breaker.assert_closed()
        assert "HALF_OPEN" in str(exc_info.value)

    def test_assert_closed_passes_when_closed(self, temp_dir, mock_bridge):
        """Test assert_closed passes when CLOSED."""
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge)
        breaker._state = BreakerState.CLOSED
        breaker.assert_closed()

    def test_reset_breaker(self, temp_dir, mock_bridge):
        """Test manual reset returns to CLOSED."""
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge)
        breaker._state = BreakerState.OPEN
        breaker._session_high_equity = 10000
        breaker.reset()
        assert breaker.state == BreakerState.CLOSED
        assert breaker._session_high_equity is None

    def test_get_status_returns_dict(self, temp_dir, mock_bridge):
        """Test get_status returns correct dict."""
        breaker = self._make_breaker(
            temp_dir,
            bridge=mock_bridge,
            config={"max_session_drawdown_pct": 3.0, "cooldown_seconds": 60},
        )
        status = breaker.get_status()
        assert "state" in status
        assert "max_session_drawdown_pct" in status
        assert "cooldown_seconds" in status
        assert status["state"] == "closed"
        assert status["max_session_drawdown_pct"] == 3.0

    @pytest.mark.asyncio
    async def test_monitor_loop_checks_drawdown(self, temp_dir, mock_bridge):
        """Test monitor loop detects drawdown and trips breaker."""
        mock_bridge.account_info = AsyncMock(return_value={"equity": 9700})
        breaker = self._make_breaker(
            temp_dir,
            bridge=mock_bridge,
            config={"max_session_drawdown_pct": 3.0, "cooldown_seconds": 60},
        )
        breaker._session_high_equity = 10000
        breaker._state = BreakerState.CLOSED
        breaker._monitoring = True

        monitor_task = asyncio.create_task(breaker._monitor_loop())
        await asyncio.sleep(0.05)
        breaker._monitoring = False
        await monitor_task
        assert breaker.state == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_monitor_loop_handles_exception(self, temp_dir, mock_bridge):
        """Test monitor loop handles bridge exceptions."""
        mock_bridge.account_info = AsyncMock(side_effect=Exception("Connection error"))
        breaker = self._make_breaker(temp_dir, bridge=mock_bridge)
        breaker._session_high_equity = 10000
        breaker._monitoring = True
        monitor_task = asyncio.create_task(breaker._monitor_loop())
        await asyncio.sleep(0.05)
        breaker._monitoring = False
        await monitor_task
        assert breaker._monitoring is False


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = MagicMock()
        return bridge

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_full_trip_and_cooldown_cycle(self, temp_dir, mock_bridge):
        """Test complete trip -> cooldown -> half_open cycle."""
        audit = AuditEngine(Path(temp_dir) / "audit.jsonl")
        storage = Path(temp_dir) / "state.json"
        config = {"max_session_drawdown_pct": 3.0, "cooldown_seconds": 0}
        breaker = DrawdownCircuitBreaker(
            config=config, bridge=mock_bridge, audit=audit, storage_path=storage
        )

        assert breaker.state == BreakerState.CLOSED

        await breaker._trip_breaker(5.0, 9500)
        assert breaker.state == BreakerState.OPEN

        await asyncio.sleep(0.05)
        assert breaker.state == BreakerState.HALF_OPEN
