"""Unit tests for preflight module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synx_mt5.risk.preflight import OrderRequest, PreFlightResult, PreFlightValidator


class TestOrderRequest:
    """Test OrderRequest dataclass."""

    def test_order_request_creation(self):
        """Test OrderRequest creation with all fields."""
        req = OrderRequest(
            symbol="EURUSD",
            volume=0.1,
            order_type="ORDER_TYPE_BUY",
            price=1.08500,
            sl=1.08000,
            tp=1.09000,
            comment="Test comment",
            magic=12345,
        )
        assert req.symbol == "EURUSD"
        assert req.volume == 0.1
        assert req.order_type == "ORDER_TYPE_BUY"
        assert req.price == 1.08500
        assert req.sl == 1.08000
        assert req.tp == 1.09000
        assert req.comment == "Test comment"
        assert req.magic == 12345

    def test_order_request_defaults(self):
        """Test OrderRequest default values."""
        req = OrderRequest(symbol="EURUSD", volume=0.1, order_type="BUY", price=1.085)
        assert req.sl is None
        assert req.tp is None
        assert req.comment is None
        assert req.magic == 0


class TestPreFlightResult:
    """Test PreFlightResult dataclass."""

    def test_preflight_result_passed(self):
        """Test PreFlightResult with passed=True."""
        result = PreFlightResult(passed=True)
        assert result.passed is True
        assert result.reason is None
        assert result.warnings == []

    def test_preflight_result_failed(self):
        """Test PreFlightResult with passed=False."""
        result = PreFlightResult(passed=False, reason="Invalid symbol")
        assert result.passed is False
        assert result.reason == "Invalid symbol"
        assert result.warnings == []

    def test_preflight_result_with_warnings(self):
        """Test PreFlightResult with warnings."""
        result = PreFlightResult(passed=True, warnings=["Warning 1", "Warning 2"])
        assert result.passed is True
        assert len(result.warnings) == 2

    def test_preflight_result_warnings_default(self):
        """Test PreFlightResult warnings default to empty list."""
        result = PreFlightResult(passed=True)
        assert result.warnings == []


class TestPreFlightValidator:
    """Test PreFlightValidator class."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = MagicMock()
        return bridge

    @pytest.fixture
    def validator(self, mock_bridge):
        """Create validator instance."""
        config = {"require_sl": True, "min_sl_pips": 5, "min_rr_ratio": 1.0}
        return PreFlightValidator(config=config, bridge=mock_bridge)

    @pytest.mark.asyncio
    async def test_validate_valid_order(self, validator, mock_bridge):
        """Test validate with valid order passes."""
        mock_bridge.symbol_info = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "trade_mode": 2,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "point": 0.00001,
            }
        )
        mock_bridge.symbol_info_tick = AsyncMock(return_value={"ask": 1.08550, "bid": 1.08500})
        mock_bridge.account_info = AsyncMock(return_value={"trade_mode": 0})

        req = OrderRequest(
            symbol="EURUSD", volume=0.1, order_type="ORDER_TYPE_BUY", price=1.08550, sl=1.08000
        )
        result = await validator.validate(req)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_invalid_symbol(self, validator, mock_bridge):
        """Test validate with invalid symbol fails."""
        mock_bridge.symbol_info = AsyncMock(return_value=None)

        req = OrderRequest(symbol="INVALID_SYMBOL", volume=0.1, order_type="BUY", price=1.085)
        result = await validator.validate(req)

        assert result.passed is False
        assert "not found" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_validate_symbol_not_tradeable(self, validator, mock_bridge):
        """Test validate with non-tradeable symbol fails."""
        mock_bridge.symbol_info = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "trade_mode": 0,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "point": 0.00001,
            }
        )

        req = OrderRequest(symbol="EURUSD", volume=0.1, order_type="BUY", price=1.085)
        result = await validator.validate(req)

        assert result.passed is False
        assert "not currently tradeable" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_validate_volume_too_high(self, validator, mock_bridge):
        """Test validate with volume exceeding maximum."""
        mock_bridge.symbol_info = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "trade_mode": 2,
                "volume_min": 0.01,
                "volume_max": 50.0,
                "point": 0.00001,
            }
        )
        mock_bridge.account_info = AsyncMock(return_value={"trade_mode": 0})

        req = OrderRequest(symbol="EURUSD", volume=100.0, order_type="BUY", price=1.085)
        result = await validator.validate(req)

        assert result.passed is False
        assert "exceeds maximum" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_validate_volume_too_low(self, validator, mock_bridge):
        """Test validate with volume below minimum."""
        mock_bridge.symbol_info = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "trade_mode": 2,
                "volume_min": 0.1,
                "volume_max": 100.0,
                "point": 0.00001,
            }
        )

        req = OrderRequest(symbol="EURUSD", volume=0.01, order_type="BUY", price=1.085)
        result = await validator.validate(req)

        assert result.passed is False
        assert "below minimum" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_validate_missing_sl_for_live_account(self, validator, mock_bridge):
        """Test validate fails when SL required but not provided for live account."""
        mock_bridge.symbol_info = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "trade_mode": 2,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "point": 0.00001,
            }
        )
        mock_bridge.account_info = AsyncMock(return_value={"trade_mode": 1})

        req = OrderRequest(symbol="EURUSD", volume=0.1, order_type="BUY", price=1.085, sl=None)
        result = await validator.validate(req)

        assert result.passed is False
        assert "stop loss" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_validate_sl_too_tight(self, validator, mock_bridge):
        """Test validate fails when SL distance is too tight."""
        mock_bridge.symbol_info = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "trade_mode": 2,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "point": 0.00001,
            }
        )
        mock_bridge.symbol_info_tick = AsyncMock(return_value={"ask": 1.08550, "bid": 1.08500})
        mock_bridge.account_info = AsyncMock(return_value={"trade_mode": 0})

        req = OrderRequest(
            symbol="EURUSD", volume=0.1, order_type="ORDER_TYPE_BUY", price=1.08550, sl=1.08548
        )
        result = await validator.validate(req)

        assert result.passed is False
        assert "below minimum" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_validate_demo_account_no_sl_required(self, mock_bridge):
        """Test validate passes for demo account without SL."""
        config = {"require_sl": True, "min_sl_pips": 5}
        validator = PreFlightValidator(config=config, bridge=mock_bridge)

        mock_bridge.symbol_info = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "trade_mode": 2,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "point": 0.00001,
            }
        )
        mock_bridge.account_info = AsyncMock(return_value={"trade_mode": 0})

        req = OrderRequest(symbol="EURUSD", volume=0.1, order_type="BUY", price=1.085, sl=None)
        result = await validator.validate(req)

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_comment_truncation(self, validator, mock_bridge):
        """Test validate truncates comment to 31 chars."""
        mock_bridge.symbol_info = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "trade_mode": 2,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "point": 0.00001,
            }
        )
        mock_bridge.symbol_info_tick = AsyncMock(return_value={"ask": 1.08550, "bid": 1.08500})
        mock_bridge.account_info = AsyncMock(return_value={"trade_mode": 0})

        long_comment = "A" * 50
        req = OrderRequest(
            symbol="EURUSD",
            volume=0.1,
            order_type="ORDER_TYPE_BUY",
            price=1.08550,
            sl=1.08000,
            comment=long_comment,
        )
        result = await validator.validate(req)

        assert result.passed is True
        assert any("truncated" in w.lower() for w in result.warnings)
        assert len(req.comment) <= 31


class TestPreFlightValidatorRR:
    """Test risk-reward ratio validation."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = MagicMock()
        return bridge

    @pytest.mark.asyncio
    async def test_validate_rr_ratio_warning(self, mock_bridge):
        """Test validate issues warning for low R:R ratio."""
        config = {"require_sl": True, "min_sl_pips": 5, "min_rr_ratio": 2.0}
        validator = PreFlightValidator(config=config, bridge=mock_bridge)

        mock_bridge.symbol_info = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "trade_mode": 2,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "point": 0.00001,
            }
        )
        mock_bridge.symbol_info_tick = AsyncMock(return_value={"ask": 1.08550, "bid": 1.08500})
        mock_bridge.account_info = AsyncMock(return_value={"trade_mode": 0})

        req = OrderRequest(
            symbol="EURUSD",
            volume=0.1,
            order_type="ORDER_TYPE_BUY",
            price=1.08550,
            sl=1.08000,
            tp=1.08700,
        )
        result = await validator.validate(req)

        assert result.passed is True
        assert any("r:r ratio" in w.lower() for w in result.warnings)
