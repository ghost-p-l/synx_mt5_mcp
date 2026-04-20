"""Unit tests for position sizing module."""

import pytest

from synx_mt5.risk.preflight import OrderRequest
from synx_mt5.risk.sizing import PositionSizingEngine


class TestPositionSizingEngine:
    """Test PositionSizingEngine class."""

    @pytest.fixture
    def engine(self):
        """Create sizing engine with default config."""
        config = {
            "max_risk_per_trade_pct": 1.0,
            "max_total_exposure_pct": 10.0,
            "max_positions_per_symbol": 3,
            "max_total_positions": 10,
        }
        return PositionSizingEngine(config=config)

    @pytest.fixture
    def sample_account(self):
        """Create sample account data."""
        return {"equity": 10000.0}

    @pytest.fixture
    def sample_symbol_info(self):
        """Create sample symbol info."""
        return {
            "trade_tick_value": 10.0,
            "trade_tick_size": 0.0001,
            "ask": 1.08550,
        }

    def test_init_default_values(self):
        """Test init with default values."""
        engine = PositionSizingEngine({})
        assert engine.max_risk_per_trade_pct == 1.0
        assert engine.max_total_exposure_pct == 10.0
        assert engine.max_positions_per_symbol == 3
        assert engine.max_total_positions == 10

    def test_init_custom_values(self):
        """Test init with custom values."""
        config = {
            "max_risk_per_trade_pct": 2.0,
            "max_total_exposure_pct": 20.0,
            "max_positions_per_symbol": 5,
            "max_total_positions": 20,
        }
        engine = PositionSizingEngine(config)
        assert engine.max_risk_per_trade_pct == 2.0
        assert engine.max_total_exposure_pct == 20.0
        assert engine.max_positions_per_symbol == 5
        assert engine.max_total_positions == 20

    @pytest.mark.asyncio
    async def test_check_and_cap_volume_no_positions(
        self, engine, sample_account, sample_symbol_info
    ):
        """Test with no existing positions."""
        req = OrderRequest(symbol="EURUSD", volume=0.1, order_type="BUY", price=1.08550, sl=1.08000)
        positions = []

        volume, warnings = await engine.check_and_cap_volume(
            req, sample_account, positions, sample_symbol_info
        )

        assert volume == 0.1
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_check_and_cap_volume_raises_max_positions(
        self, engine, sample_account, sample_symbol_info
    ):
        """Test raises when max total positions reached."""
        req = OrderRequest(symbol="EURUSD", volume=0.1, order_type="BUY", price=1.08550)
        positions = [
            {"symbol": "GBPUSD"},
            {"symbol": "USDJPY"},
            {"symbol": "AUDUSD"},
            {"symbol": "USDCAD"},
            {"symbol": "EURGBP"},
            {"symbol": "EURJPY"},
            {"symbol": "EURCHF"},
            {"symbol": "EURAUD"},
            {"symbol": "EURCAD"},
            {"symbol": "EURJPY"},
        ]

        with pytest.raises(ValueError) as exc_info:
            await engine.check_and_cap_volume(req, sample_account, positions, sample_symbol_info)
        assert "Max positions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_and_cap_volume_raises_max_symbol_positions(
        self, engine, sample_account, sample_symbol_info
    ):
        """Test raises when max positions per symbol reached."""
        req = OrderRequest(symbol="EURUSD", volume=0.1, order_type="BUY", price=1.08550)
        positions = [
            {"symbol": "EURUSD", "ticket": 1},
            {"symbol": "EURUSD", "ticket": 2},
            {"symbol": "EURUSD", "ticket": 3},
        ]

        with pytest.raises(ValueError) as exc_info:
            await engine.check_and_cap_volume(req, sample_account, positions, sample_symbol_info)
        assert "Max positions for EURUSD" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_and_cap_volume_caps_volume_by_risk(self, engine, sample_account):
        """Test volume is capped when risk would be exceeded."""
        symbol_info = {
            "trade_tick_value": 10.0,
            "trade_tick_size": 0.0001,
            "ask": 1.08550,
        }
        req = OrderRequest(symbol="EURUSD", volume=1.0, order_type="BUY", price=1.08550, sl=1.08000)
        positions = []

        volume, warnings = await engine.check_and_cap_volume(
            req, sample_account, positions, symbol_info
        )

        assert volume < 1.0
        assert any("capped" in w.lower() for w in warnings)

    @pytest.mark.asyncio
    async def test_check_and_cap_volume_zero_equity(self, engine, sample_symbol_info):
        """Test with zero equity returns zero volume."""
        account = {"equity": 0}
        req = OrderRequest(symbol="EURUSD", volume=0.1, order_type="BUY", price=1.08550, sl=1.08000)
        positions = []

        volume, warnings = await engine.check_and_cap_volume(
            req, account, positions, sample_symbol_info
        )

        assert volume == 0.0
        assert len(warnings) == 1

    @pytest.mark.asyncio
    async def test_check_and_cap_volume_low_equity(self, engine, sample_symbol_info):
        """Test with low equity is capped."""
        account = {"equity": 1000.0}
        req = OrderRequest(symbol="EURUSD", volume=0.1, order_type="BUY", price=1.08550, sl=1.08000)
        positions = []

        volume, warnings = await engine.check_and_cap_volume(
            req, account, positions, sample_symbol_info
        )

        assert volume <= 0.1
        assert len(warnings) == 1

    @pytest.mark.asyncio
    async def test_check_and_cap_volume_with_custom_risk(self, sample_account, sample_symbol_info):
        """Test with custom risk percentage."""
        config = {
            "max_risk_per_trade_pct": 0.5,
            "max_total_exposure_pct": 10.0,
            "max_positions_per_symbol": 3,
            "max_total_positions": 10,
        }
        engine = PositionSizingEngine(config)
        req = OrderRequest(symbol="EURUSD", volume=2.0, order_type="BUY", price=1.08550, sl=1.08000)
        positions = []

        volume, warnings = await engine.check_and_cap_volume(
            req, sample_account, positions, sample_symbol_info
        )

        assert volume < 2.0


class TestPositionSizingEdgeCases:
    """Test edge cases for position sizing."""

    @pytest.mark.asyncio
    async def test_zero_tick_value(self):
        """Test with zero tick value."""
        config = {
            "max_risk_per_trade_pct": 1.0,
            "max_total_exposure_pct": 10.0,
            "max_positions_per_symbol": 3,
            "max_total_positions": 10,
        }
        engine = PositionSizingEngine(config)

        account = {"equity": 10000}
        symbol_info = {"trade_tick_value": 0, "trade_tick_size": 0.0001, "ask": 1.08550}
        req = OrderRequest(symbol="EURUSD", volume=1.0, order_type="BUY", price=1.08550, sl=1.08000)
        positions = []

        volume, warnings = await engine.check_and_cap_volume(req, account, positions, symbol_info)
        assert volume == 1.0
