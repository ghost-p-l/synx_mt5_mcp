"""Unit tests for risk module."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from synx_mt5.risk.circuit_breaker import BreakerState, DrawdownCircuitBreaker
from synx_mt5.risk.hitl import HITLGate
from synx_mt5.risk.preflight import OrderRequest


class TestDrawdownCircuitBreaker:
    """Test circuit breaker."""

    @pytest.fixture
    def breaker(self):
        import tempfile
        from pathlib import Path

        from synx_mt5.audit.engine import AuditEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            audit = AuditEngine(Path(tmpdir) / "audit.jsonl")
            breaker = DrawdownCircuitBreaker(
                config={"max_session_drawdown_pct": 5.0, "cooldown_seconds": 60},
                bridge=None,
                audit=audit,
            )
            yield breaker

    def test_initial_state_closed(self, breaker):
        """Test that breaker starts closed."""
        assert breaker.state == BreakerState.CLOSED

    def test_assert_closed_raises_when_open(self, breaker):
        """Test that assert raises when breaker is open."""
        breaker.state = BreakerState.OPEN
        with pytest.raises(RuntimeError):
            breaker.assert_closed()

    def test_reset(self, breaker):
        """Test manual reset."""
        breaker.state = BreakerState.OPEN
        breaker.reset()
        assert breaker.state == BreakerState.CLOSED

    def test_get_status(self, breaker):
        """Test status reporting."""
        status = breaker.get_status()
        assert "state" in status
        assert "max_session_drawdown_pct" in status


class TestHITLGate:
    """Test human-in-the-loop gate."""

    @pytest.fixture
    def gate(self):
        import tempfile
        from pathlib import Path

        from synx_mt5.audit.engine import AuditEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            audit = AuditEngine(Path(tmpdir) / "audit.jsonl")
            gate = HITLGate(
                config={"enabled": True, "timeout_seconds": 5},
                audit=audit,
            )
            yield gate

    @pytest.fixture
    def sample_request(self):
        return OrderRequest(
            symbol="EURUSD",
            volume=0.1,
            order_type="ORDER_TYPE_BUY",
            price=1.08500,
            sl=1.08000,
            tp=1.09000,
        )

    @pytest.mark.asyncio
    async def test_auto_approve_when_disabled(self):
        """Test that requests are auto-approved when HITL is disabled."""
        import tempfile
        from pathlib import Path

        from synx_mt5.audit.engine import AuditEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            audit = AuditEngine(Path(tmpdir) / "audit.jsonl")
            gate = HITLGate(
                config={"enabled": False},
                audit=audit,
            )
            req = OrderRequest("EURUSD", 0.1, "BUY", 1.085)
            result = await gate.request_approval(req)
            assert result == "auto_approved"

    @pytest.mark.asyncio
    async def test_approve_pending(self, gate, sample_request):
        """Test approving a pending request."""
        gate._emit = AsyncMock()
        approval_task = asyncio.create_task(gate.request_approval(sample_request))
        await asyncio.sleep(0.1)
        pending_before = gate.get_pending()
        assert pending_before["count"] == 1
        approval_id = pending_before["pending"][0]
        gate.approve(approval_id)
        await asyncio.wait_for(approval_task, timeout=2.0)
        pending = gate.get_pending()
        assert pending["count"] == 0

    @pytest.mark.asyncio
    async def test_reject_pending(self, gate, sample_request):
        """Test rejecting a pending request."""
        gate._emit = AsyncMock()
        approval_task = asyncio.create_task(gate.request_approval(sample_request))
        await asyncio.sleep(0.1)
        pending_before = gate.get_pending()
        assert pending_before["count"] == 1
        approval_id = pending_before["pending"][0]
        gate.reject(approval_id)
        await asyncio.wait_for(approval_task, timeout=2.0)
        pending = gate.get_pending()
        assert pending["count"] == 0


class TestPreFlightValidator:
    """Test pre-flight validator."""

    def test_order_request_dataclass(self):
        """Test OrderRequest creation."""
        req = OrderRequest(
            symbol="EURUSD",
            volume=0.1,
            order_type="ORDER_TYPE_BUY",
            price=1.08500,
            sl=1.08000,
            tp=1.09000,
        )
        assert req.symbol == "EURUSD"
        assert req.volume == 0.1
