"""Unit tests for HITL module."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from synx_mt5.audit.engine import AuditEngine
from synx_mt5.risk.hitl import HITLGate
from synx_mt5.risk.preflight import OrderRequest


class TestHITLGate:
    """Test HITLGate class."""

    @pytest.fixture
    def audit_engine(self, tmp_path):
        """Create audit engine for tests."""
        yield AuditEngine(tmp_path / "audit.jsonl")

    @pytest.fixture
    def gate(self, audit_engine, tmp_path):
        """Create gate instance with enabled."""
        config = {"enabled": True, "timeout_seconds": 5}
        return HITLGate(config=config, audit=audit_engine, storage_path=tmp_path)

    @pytest.fixture
    def disabled_gate(self, audit_engine, tmp_path):
        """Create gate instance disabled."""
        config = {"enabled": False, "timeout_seconds": 5}
        return HITLGate(config=config, audit=audit_engine, storage_path=tmp_path)

    @pytest.fixture
    def sample_request(self):
        """Create sample order request."""
        return OrderRequest(
            symbol="EURUSD",
            volume=0.1,
            order_type="ORDER_TYPE_BUY",
            price=1.08500,
            sl=1.08000,
            tp=1.09000,
        )

    def test_init_enabled(self, audit_engine, tmp_path):
        """Test init with enabled=True."""
        config = {"enabled": True, "timeout_seconds": 300, "sink": "terminal"}
        gate = HITLGate(config=config, audit=audit_engine, storage_path=tmp_path)
        assert gate.enabled is True
        assert gate.timeout_secs == 300
        assert gate.sink == "terminal"

    def test_init_disabled(self, audit_engine, tmp_path):
        """Test init with enabled=False."""
        config = {"enabled": False}
        gate = HITLGate(config=config, audit=audit_engine, storage_path=tmp_path)
        assert gate.enabled is False

    def test_init_defaults(self, audit_engine, tmp_path):
        """Test init with default values."""
        config = {}
        gate = HITLGate(config=config, audit=audit_engine, storage_path=tmp_path)
        assert gate.enabled is True
        assert gate.timeout_secs == 300

    @pytest.mark.asyncio
    async def test_request_approval_generates_approval_id(self, gate, sample_request):
        """Test request_approval generates unique approval_id."""
        gate._emit = AsyncMock()
        approval_task = asyncio.create_task(gate.request_approval(sample_request))
        await asyncio.sleep(0.05)
        pending = gate.get_pending()
        approval_id = pending["pending"][0]
        gate.approve(approval_id)
        result = await asyncio.wait_for(approval_task, timeout=1.0)
        assert result is not None
        assert len(result) == 16
        assert result != "auto_approved"

    @pytest.mark.asyncio
    async def test_request_approval_stores_in_pending(self, gate, sample_request):
        """Test request_approval stores request in pending dict."""
        gate._emit = AsyncMock()
        approval_task = asyncio.create_task(gate.request_approval(sample_request))
        await asyncio.sleep(0.05)
        pending = gate.get_pending()
        assert pending["count"] == 1
        approval_id = pending["pending"][0]
        gate.approve(approval_id)
        await asyncio.wait_for(approval_task, timeout=1.0)

    @pytest.mark.asyncio
    async def test_request_approval_when_disabled(self, disabled_gate, sample_request):
        """Test request_approval returns auto_approved when disabled."""
        result = await disabled_gate.request_approval(sample_request)
        assert result == "auto_approved"
        pending = disabled_gate.get_pending()
        assert pending["count"] == 0

    def test_approve_removes_from_pending(self, gate):
        """Test approve removes approval from pending."""
        gate._pending["test_approval_123"] = OrderRequest(
            symbol="EURUSD", volume=0.1, order_type="BUY", price=1.085
        )
        result = gate.approve("test_approval_123")
        assert result is True
        pending = gate.get_pending()
        assert pending["count"] == 0

    def test_approve_returns_true(self, gate):
        """Test approve returns True for valid approval_id."""
        gate._pending["test_approval_123"] = OrderRequest(
            symbol="EURUSD", volume=0.1, order_type="BUY", price=1.085
        )
        result = gate.approve("test_approval_123")
        assert result is True

    def test_approve_nonexistent_returns_false(self, gate):
        """Test approve returns False for non-existent approval_id."""
        result = gate.approve("nonexistent_id")
        assert result is False
        pending = gate.get_pending()
        assert pending["count"] == 0

    def test_reject_removes_from_pending(self, gate):
        """Test reject removes approval from pending."""
        gate._pending["test_approval_456"] = OrderRequest(
            symbol="EURUSD", volume=0.1, order_type="SELL", price=1.085
        )
        result = gate.reject("test_approval_456")
        assert result is True
        pending = gate.get_pending()
        assert pending["count"] == 0

    def test_reject_returns_true(self, gate):
        """Test reject returns True for valid approval_id."""
        gate._pending["test_approval_456"] = OrderRequest(
            symbol="EURUSD", volume=0.1, order_type="SELL", price=1.085
        )
        result = gate.reject("test_approval_456")
        assert result is True

    def test_reject_nonexistent_returns_false(self, gate):
        """Test reject returns False for non-existent approval_id."""
        result = gate.reject("nonexistent_id")
        assert result is False
        pending = gate.get_pending()
        assert pending["count"] == 0

    def test_get_status_empty(self, gate):
        """Test get_status with no pending."""
        status = gate.get_pending()
        assert status["count"] == 0
        assert status["pending"] == []

    def test_get_status_multiple_pending(self, gate):
        """Test get_status with multiple pending approvals."""
        gate._pending["id1"] = OrderRequest(
            symbol="EURUSD", volume=0.1, order_type="BUY", price=1.085
        )
        gate._pending["id2"] = OrderRequest(
            symbol="GBPUSD", volume=0.2, order_type="SELL", price=1.265
        )
        gate._pending["id3"] = OrderRequest(
            symbol="XAUUSD", volume=0.01, order_type="BUY", price=2050.0
        )

        status = gate.get_pending()
        assert status["count"] == 3
        assert len(status["pending"]) == 3

    @pytest.mark.asyncio
    async def test_request_approval_approves_and_returns(self, gate, sample_request):
        """Test full flow: request -> approve -> returns."""
        gate._emit = AsyncMock()
        approval_task = asyncio.create_task(gate.request_approval(sample_request))
        await asyncio.sleep(0.05)

        pending = gate.get_pending()
        approval_id = pending["pending"][0]

        gate.approve(approval_id)
        result = await asyncio.wait_for(approval_task, timeout=1.0)
        assert result == approval_id

    @pytest.mark.asyncio
    async def test_request_approval_rejects_and_returns(self, gate, sample_request):
        """Test full flow: request -> reject -> returns."""
        gate._emit = AsyncMock()
        approval_task = asyncio.create_task(gate.request_approval(sample_request))
        await asyncio.sleep(0.05)

        pending = gate.get_pending()
        approval_id = pending["pending"][0]

        gate.reject(approval_id)
        result = await asyncio.wait_for(approval_task, timeout=1.0)
        assert result == approval_id

    def test_approve_logs_audit(self, gate, audit_engine):
        """Test approve logs to audit."""
        gate._pending["test_id"] = OrderRequest(
            symbol="EURUSD", volume=0.1, order_type="BUY", price=1.085
        )
        gate.approve("test_id")
        records = audit_engine.get_records()
        assert len(records) == 1
        assert records[0]["event"] == "risk.hitl_approved"

    def test_reject_logs_audit(self, gate, audit_engine):
        """Test reject logs to audit."""
        gate._pending["test_id"] = OrderRequest(
            symbol="EURUSD", volume=0.1, order_type="BUY", price=1.085
        )
        gate.reject("test_id")
        records = audit_engine.get_records()
        assert len(records) == 1
        assert records[0]["event"] == "risk.hitl_rejected"


class TestHITLFormatMessage:
    """Test message formatting."""

    @pytest.fixture
    def audit_engine(self, tmp_path):
        """Create audit engine for tests."""
        yield AuditEngine(tmp_path / "audit.jsonl")

    def test_format_message_content(self, audit_engine, tmp_path):
        """Test _format_message produces expected output."""
        config = {"enabled": True}
        gate = HITLGate(config=config, audit=audit_engine, storage_path=tmp_path)

        req = OrderRequest(
            symbol="EURUSD",
            volume=0.1,
            order_type="ORDER_TYPE_BUY",
            price=1.08500,
            sl=1.08000,
            tp=1.09000,
        )
        msg = gate._format_message("test_approval_id", req)

        assert "test_approval_id" in msg
        assert "EURUSD" in msg
        assert "0.1" in msg
        assert "1.085" in msg
        assert "1.08" in msg
        assert "1.09" in msg

    def test_format_message_with_none_sl_tp(self, audit_engine, tmp_path):
        """Test _format_message with None SL and TP."""
        config = {"enabled": True}
        gate = HITLGate(config=config, audit=audit_engine, storage_path=tmp_path)

        req = OrderRequest(
            symbol="EURUSD",
            volume=0.1,
            order_type="ORDER_TYPE_BUY",
            price=1.08500,
            sl=None,
            tp=None,
        )
        msg = gate._format_message("test_id", req)
        assert "None" in msg
