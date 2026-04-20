"""Unit tests for terminal management tools."""

from unittest.mock import AsyncMock

import pytest

from synx_mt5.tools.terminal_mgmt import (
    OrderCalcMarginInput,
    OrderCalcProfitInput,
    OrderCheckInput,
    SymbolSelectInput,
    TerminalInfoOutput,
    TerminalMgmtService,
    handle_order_calc_margin,
    handle_order_calc_profit,
    handle_order_check,
    handle_symbol_select,
    handle_terminal_get_common_path,
    handle_terminal_get_data_path,
    handle_terminal_get_info,
)


class MockAuditEngine:
    def __init__(self):
        self.events = []

    def log(self, event_type, data):
        self.events.append((event_type, data))


class MockBridge:
    def __init__(self, terminal_data=None):
        self._terminal_data = terminal_data or {
            "version": "5.00.5735",
            "build": 4445,
            "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
            "data_path": "C:\\Users\\Test\\AppData\\Roaming\\MetaTrader 5",
            "community_account": "123456",
            "community_balance": 0.0,
            "connected": True,
            "trade_allowed": True,
            "trade_expert": True,
            "dlls_allowed": False,
            "mqid": True,
            "ping_last": 45,
            "language": "English",
            "company": "Demo Broker",
            "name": "MetaTrader 5",
        }

    async def terminal_info(self):
        return self._terminal_data

    async def symbol_select(self, symbol, enable):
        return True

    async def order_calc_margin(self, order_type, symbol, volume, price):
        return {"margin": volume * price * 0.01, "currency": "USD"}

    async def order_calc_profit(self, order_type, symbol, volume, price_open, price_close):
        return {"profit": (price_close - price_open) * volume * 100000, "currency": "USD"}

    async def order_check(self, symbol, order_type, volume, price, sl, tp):
        return {
            "retcode": 0,
            "comment": "No error",
            "balance": 10000.0,
            "equity": 10500.0,
            "profit": 0.0,
            "margin": 108.5,
            "margin_free": 10391.5,
            "margin_level": 9677.8,
        }

    async def symbol_info(self, symbol):
        return {"point": 0.00001, "digits": 5, "trade_tick_value": 10.0}


@pytest.fixture
def mock_audit():
    return MockAuditEngine()


@pytest.fixture
def mock_bridge():
    return MockBridge()


@pytest.fixture
def service(mock_bridge, mock_audit):
    return TerminalMgmtService(bridge=mock_bridge, audit=mock_audit)


class TestTerminalMgmtService:
    @pytest.mark.asyncio
    async def test_get_terminal_info(self, service, mock_audit):
        result = await service.get_terminal_info()
        assert isinstance(result, TerminalInfoOutput)
        assert result.version == "5.00.5735"
        assert result.build == 4445
        assert result.connected is True
        assert result.trade_allowed is True
        assert result.trade_expert is True
        assert len(mock_audit.events) == 1

    @pytest.mark.asyncio
    async def test_get_terminal_info_disconnected(self, mock_bridge, mock_audit):
        mock_bridge._terminal_data["connected"] = False
        mock_bridge._terminal_data["trade_allowed"] = False
        service = TerminalMgmtService(bridge=mock_bridge, audit=mock_audit)
        result = await service.get_terminal_info()
        assert result.connected is False
        assert result.trade_allowed is False

    @pytest.mark.asyncio
    async def test_symbol_select(self, service, mock_audit):
        result = await service.symbol_select("EURUSD", enable=True)
        assert result["symbol"] == "EURUSD"
        assert result["selected"] is True
        assert len(mock_audit.events) == 1

    @pytest.mark.asyncio
    async def test_symbol_select_disable(self, service, mock_audit):
        result = await service.symbol_select("EURUSD", enable=False)
        assert result["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_order_calc_margin(self, service, mock_audit):
        result = await service.order_calc_margin(
            order_type="ORDER_TYPE_BUY",
            symbol="EURUSD",
            volume=0.1,
            price=1.0850,
        )
        assert result["margin"] is not None
        assert result["currency"] == "USD"
        assert result["symbol"] == "EURUSD"
        assert len(mock_audit.events) == 1

    @pytest.mark.asyncio
    async def test_order_calc_margin_null_result(self, mock_bridge, mock_audit):
        mock_bridge.order_calc_margin = AsyncMock(return_value=None)
        service = TerminalMgmtService(bridge=mock_bridge, audit=mock_audit)
        result = await service.order_calc_margin("ORDER_TYPE_BUY", "EURUSD", 0.1, 1.085)
        assert result["margin"] is None
        assert result["currency"] is None

    @pytest.mark.asyncio
    async def test_order_calc_profit(self, service, mock_audit):
        result = await service.order_calc_profit(
            order_type="ORDER_TYPE_BUY",
            symbol="EURUSD",
            volume=0.1,
            price_open=1.0800,
            price_close=1.0850,
        )
        assert result["profit"] is not None
        assert result["currency"] == "USD"
        assert result["pips"] > 0
        assert len(mock_audit.events) == 1

    @pytest.mark.asyncio
    async def test_order_check(self, service, mock_audit):
        result = await service.order_check(
            symbol="EURUSD",
            volume=0.1,
            order_type="ORDER_TYPE_BUY",
            price=1.0850,
            sl=1.0800,
            tp=1.0900,
        )
        assert result["retcode"] == 0
        assert result["balance"] == 10000.0
        assert result["margin"] == 108.5
        assert result["margin_free"] == 10391.5
        assert len(mock_audit.events) == 1

    @pytest.mark.asyncio
    async def test_order_check_error(self, mock_bridge, mock_audit):
        mock_bridge.order_check = AsyncMock(
            return_value={"retcode": 4756, "comment": "No connection", "balance": 0.0}
        )
        service = TerminalMgmtService(bridge=mock_bridge, audit=mock_audit)
        result = await service.order_check("EURUSD", "ORDER_TYPE_BUY", 0.1, 1.085, 0, 0)
        assert result["retcode"] == 4756


class TestHandlerFunctions:
    @pytest.mark.asyncio
    async def test_handle_terminal_get_info(self, service):
        result = await handle_terminal_get_info(service, {})
        assert result["version"] == "5.00.5735"
        assert result["build"] == 4445

    @pytest.mark.asyncio
    async def test_handle_terminal_get_data_path(self, service):
        result = await handle_terminal_get_data_path(service, {})
        assert "data_path" in result
        assert "MetaTrader 5" in result["data_path"]

    @pytest.mark.asyncio
    async def test_handle_terminal_get_common_path(self, service):
        result = await handle_terminal_get_common_path(service, {})
        assert "common_path" in result

    @pytest.mark.asyncio
    async def test_handle_symbol_select(self, service):
        result = await handle_symbol_select(service, {"symbol": "GBPUSD", "enable": True})
        assert result["symbol"] == "GBPUSD"
        assert result["selected"] is True

    @pytest.mark.asyncio
    async def test_handle_order_calc_margin(self, service):
        result = await handle_order_calc_margin(
            service,
            {
                "order_type": "ORDER_TYPE_SELL",
                "symbol": "EURUSD",
                "volume": 0.5,
                "price": 1.0900,
            },
        )
        assert "margin" in result
        assert result["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_handle_order_calc_profit(self, service):
        result = await handle_order_calc_profit(
            service,
            {
                "order_type": "ORDER_TYPE_BUY",
                "symbol": "EURUSD",
                "volume": 0.1,
                "price_open": 1.0800,
                "price_close": 1.0850,
            },
        )
        assert "profit" in result
        assert result["pips"] > 0

    @pytest.mark.asyncio
    async def test_handle_order_check(self, service):
        result = await handle_order_check(
            service,
            {
                "symbol": "EURUSD",
                "volume": 0.1,
                "order_type": "ORDER_TYPE_BUY",
                "price": 1.0850,
                "sl": 1.0800,
                "tp": 1.0900,
            },
        )
        assert result["retcode"] == 0
        assert result["margin"] == 108.5


class TestInputValidation:
    def test_symbol_select_input_validation(self):
        inp = SymbolSelectInput.model_validate({"symbol": "eurusd"})
        assert inp.symbol == "EURUSD"
        assert inp.enable is True

    def test_order_calc_margin_input(self):
        inp = OrderCalcMarginInput.model_validate(
            {"order_type": "ORDER_TYPE_BUY", "symbol": "EURUSD", "volume": 0.1, "price": 1.085}
        )
        assert inp.volume > 0
        assert inp.price > 0

    def test_order_calc_margin_negative_volume(self):
        with pytest.raises(Exception):  # noqa: B017
            OrderCalcMarginInput.model_validate(
                {"order_type": "ORDER_TYPE_BUY", "symbol": "EURUSD", "volume": -0.1, "price": 1.085}
            )

    def test_order_calc_profit_input(self):
        inp = OrderCalcProfitInput.model_validate(
            {
                "order_type": "ORDER_TYPE_BUY",
                "symbol": "EURUSD",
                "volume": 0.1,
                "price_open": 1.0800,
                "price_close": 1.0850,
            }
        )
        assert inp.volume > 0

    def test_order_check_input(self):
        inp = OrderCheckInput.model_validate(
            {
                "symbol": "EURUSD",
                "volume": 0.1,
                "order_type": "ORDER_TYPE_BUY",
                "price": 1.0850,
            }
        )
        assert inp.symbol == "EURUSD"
