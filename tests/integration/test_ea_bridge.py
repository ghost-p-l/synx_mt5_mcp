"""Integration tests for EA REST bridge (Mode B)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synx_mt5.bridge.ea_rest import EARestBridge


class MockBridgeConfig:
    """Mock bridge config for testing."""

    def __init__(self):
        self.ea_host = "localhost"
        self.ea_port = 8765
        self.ea_api_key = "test_key_12345"
        self.ea_timeout_seconds = 10


@pytest.fixture
def ea_bridge():
    return EARestBridge(config=MockBridgeConfig())


class TestEAChartOperations:
    """Test EA REST bridge chart operations."""

    @pytest.mark.asyncio
    async def test_chart_list(self, ea_bridge):
        """Test listing open charts."""
        ea_bridge._get = AsyncMock(
            return_value=[
                {"chart_id": 1, "symbol": "EURUSD", "timeframe": "H1", "visible": True},
                {"chart_id": 2, "symbol": "GBPUSD", "timeframe": "M15", "visible": False},
            ]
        )
        result = await ea_bridge.ea_chart_list()
        assert len(result) == 2
        assert result[0]["chart_id"] == 1
        assert result[0]["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_chart_open(self, ea_bridge):
        """Test opening a chart."""
        ea_bridge._post = AsyncMock(return_value={"chart_id": 3})
        result = await ea_bridge.ea_chart_open("USDJPY", "M30")
        assert result["chart_id"] == 3

    @pytest.mark.asyncio
    async def test_chart_close(self, ea_bridge):
        """Test closing a chart."""
        ea_bridge._post = AsyncMock(return_value={"closed": True})
        result = await ea_bridge.ea_chart_close(chart_id=1)
        assert result["closed"] is True

    @pytest.mark.asyncio
    async def test_chart_screenshot(self, ea_bridge):
        """Test capturing a chart screenshot."""
        ea_bridge._post = AsyncMock(return_value={"image_base64": "iVBORw0KGgo="})
        result = await ea_bridge.ea_chart_screenshot(1, 1280, 720, True)
        assert result["image_base64"] == "iVBORw0KGgo="

    @pytest.mark.asyncio
    async def test_chart_navigate(self, ea_bridge):
        """Test chart navigation."""
        ea_bridge._post = AsyncMock(return_value={"navigated": True})
        result = await ea_bridge.ea_chart_navigate(1, "end", 0)
        assert result["navigated"] is True

    @pytest.mark.asyncio
    async def test_chart_indicator_add(self, ea_bridge):
        """Test adding an indicator to a chart."""
        ea_bridge._post = AsyncMock(return_value={"handle": 42})
        result = await ea_bridge.ea_chart_indicator_add(1, "RSI", 0, {"period": 14})
        assert result["handle"] == 42

    @pytest.mark.asyncio
    async def test_chart_indicator_list(self, ea_bridge):
        """Test listing chart indicators."""
        ea_bridge._get = AsyncMock(
            return_value=[
                {"name": "Moving Average", "window": 0, "handle": 10},
                {"name": "RSI", "window": 1, "handle": 11},
            ]
        )
        result = await ea_bridge.ea_chart_indicator_list(1)
        assert len(result) == 2
        assert result[0]["name"] == "Moving Average"

    @pytest.mark.asyncio
    async def test_chart_apply_template(self, ea_bridge):
        """Test applying a chart template."""
        ea_bridge._post = AsyncMock(return_value={"applied": True})
        result = await ea_bridge.ea_chart_apply_template(1, "my_template")
        assert result["applied"] is True

    @pytest.mark.asyncio
    async def test_chart_save_template(self, ea_bridge):
        """Test saving a chart template."""
        ea_bridge._post = AsyncMock(return_value={"saved": True})
        result = await ea_bridge.ea_chart_save_template(1, "new_template")
        assert result["saved"] is True

    @pytest.mark.asyncio
    async def test_chart_set_symbol_timeframe(self, ea_bridge):
        """Test setting chart symbol and timeframe."""
        ea_bridge._post = AsyncMock(return_value={})
        await ea_bridge.ea_chart_set_symbol_timeframe(1, "AUDUSD", "H4")
        ea_bridge._post.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_script(self, ea_bridge):
        """Test running an MQL5 script."""
        ea_bridge._post = AsyncMock(return_value={"executed": True, "result": "OK"})
        result = await ea_bridge.ea_run_script(1, "MyScript", {"param1": 10})
        assert result["executed"] is True


class TestEATerminalOperations:
    """Test EA REST bridge terminal operations."""

    @pytest.mark.asyncio
    async def test_terminal_info(self, ea_bridge):
        """Test terminal info retrieval."""
        ea_bridge._get = AsyncMock(
            return_value={
                "version": "5.00.4445",
                "build": 4445,
                "connected": True,
            }
        )
        result = await ea_bridge.terminal_info()
        assert result["version"] == "5.00.4445"
        assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_account_info(self, ea_bridge):
        """Test account info retrieval."""
        ea_bridge._get = AsyncMock(
            return_value={
                "login": 12345,
                "balance": 10000.0,
                "equity": 10500.0,
            }
        )
        result = await ea_bridge.account_info()
        assert result["login"] == 12345
        assert result["balance"] == 10000.0


class TestEAMarketDataOperations:
    """Test EA REST bridge market data operations."""

    @pytest.mark.asyncio
    async def test_symbol_info(self, ea_bridge):
        """Test symbol info retrieval."""
        ea_bridge._get = AsyncMock(
            return_value={
                "symbol": "EURUSD",
                "digits": 5,
                "point": 0.00001,
            }
        )
        result = await ea_bridge.symbol_info("EURUSD")
        assert result["symbol"] == "EURUSD"
        assert result["digits"] == 5

    @pytest.mark.asyncio
    async def test_symbol_info_not_found(self, ea_bridge):
        """Test symbol not found."""
        import httpx

        response = MagicMock()
        response.status_code = 404
        ea_bridge._get = AsyncMock(
            side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=response)
        )
        result = await ea_bridge.symbol_info("INVALID")
        assert result is None

    @pytest.mark.asyncio
    async def test_symbol_info_tick(self, ea_bridge):
        """Test symbol tick retrieval."""
        ea_bridge._get = AsyncMock(return_value={"bid": 1.08500, "ask": 1.08520, "volume": 1000})
        result = await ea_bridge.symbol_info_tick("EURUSD")
        assert result["bid"] == 1.08500
        assert result["ask"] == 1.08520


class TestEAOrderOperations:
    """Test EA REST bridge order operations."""

    @pytest.mark.asyncio
    async def test_order_calc_margin(self, ea_bridge):
        """Test margin calculation."""
        ea_bridge._post = AsyncMock(return_value={"margin": 108.5, "currency": "USD"})
        result = await ea_bridge.order_calc_margin("ORDER_TYPE_BUY", "EURUSD", 0.1, 1.0850)
        assert result["margin"] == 108.5
        assert result["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_order_calc_profit(self, ea_bridge):
        """Test profit calculation."""
        ea_bridge._post = AsyncMock(return_value={"profit": 500.0, "currency": "USD"})
        result = await ea_bridge.order_calc_profit("ORDER_TYPE_BUY", "EURUSD", 0.1, 1.0800, 1.0850)
        assert result["profit"] == 500.0

    @pytest.mark.asyncio
    async def test_order_check(self, ea_bridge):
        """Test order check (dry run)."""
        ea_bridge._post = AsyncMock(
            return_value={
                "retcode": 0,
                "comment": "No error",
                "margin": 108.5,
            }
        )
        result = await ea_bridge.order_check(
            "EURUSD", "ORDER_TYPE_BUY", 0.1, 1.0850, 1.0800, 1.0900
        )
        assert result["retcode"] == 0


class TestEAConnectionLifecycle:
    """Test EA REST bridge connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self, ea_bridge):
        """Test successful connection to EA REST service."""
        ea_bridge._get_client = MagicMock(
            return_value=MagicMock(get=AsyncMock(return_value=MagicMock(status_code=200)))
        )
        result = await ea_bridge.connect()
        assert result is True
        assert ea_bridge._connected is True

    @pytest.mark.asyncio
    async def test_connect_failure(self, ea_bridge):
        """Test failed connection."""
        ea_bridge._get_client = MagicMock(
            return_value=MagicMock(get=AsyncMock(side_effect=Exception("Connection refused")))
        )
        result = await ea_bridge.connect()
        assert result is False
        assert ea_bridge._connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self, ea_bridge):
        """Test disconnect."""
        ea_bridge._client = MagicMock(aclose=AsyncMock())
        ea_bridge._connected = True
        await ea_bridge.disconnect()
        assert ea_bridge._connected is False

    @pytest.mark.asyncio
    async def test_is_connected(self, ea_bridge):
        """Test connection status check."""
        ea_bridge._connected = True
        assert await ea_bridge.is_connected() is True
        ea_bridge._connected = False
        assert await ea_bridge.is_connected() is False
