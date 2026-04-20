"""Unit tests for market depth (DOM) tools."""

from unittest.mock import AsyncMock

import pytest

from synx_mt5.tools.market_depth import (
    MarketBookGetInput,
    MarketBookSubscribeInput,
    MarketBookUnsubscribeInput,
    MarketDepthService,
    handle_market_book_get,
    handle_market_book_subscribe,
    handle_market_book_unsubscribe,
)


class MockAuditEngine:
    def __init__(self):
        self.events = []

    def log(self, event_type, data):
        self.events.append((event_type, data))


class MockBridge:
    def __init__(self):
        self._book_entries = [
            {"type": 0, "price": 1.08500, "volume": 100, "volume_dbl": 1.0},
            {"type": 0, "price": 1.08490, "volume": 200, "volume_dbl": 2.0},
            {"type": 1, "price": 1.08520, "volume": 150, "volume_dbl": 1.5},
            {"type": 1, "price": 1.08530, "volume": 180, "volume_dbl": 1.8},
        ]

    async def market_book_add(self, symbol):
        return True

    async def market_book_get(self, symbol):
        return self._book_entries

    async def market_book_release(self, symbol):
        return True


@pytest.fixture
def mock_audit():
    return MockAuditEngine()


@pytest.fixture
def mock_bridge():
    return MockBridge()


@pytest.fixture
def service(mock_bridge, mock_audit):
    return MarketDepthService(bridge=mock_bridge, audit=mock_audit)


class TestMarketDepthService:
    @pytest.mark.asyncio
    async def test_subscribe(self, service, mock_audit):
        result = await service.market_book_subscribe("EURUSD")
        assert result["symbol"] == "EURUSD"
        assert result["subscribed"] is True
        assert "EURUSD" in service._subscriptions
        assert len(mock_audit.events) == 1

    @pytest.mark.asyncio
    async def test_subscribe_fails(self, mock_bridge, mock_audit):
        mock_bridge.market_book_add = AsyncMock(return_value=False)
        service = MarketDepthService(bridge=mock_bridge, audit=mock_audit)
        result = await service.market_book_subscribe("EURUSD")
        assert result["subscribed"] is False

    @pytest.mark.asyncio
    async def test_get_book_requires_subscription(self, service, mock_audit):
        result = await service.market_book_get("EURUSD")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_book_after_subscribe(self, service, mock_audit):
        await service.market_book_subscribe("EURUSD")
        result = await service.market_book_get("EURUSD")
        assert result is not None
        assert result.symbol == "EURUSD"
        assert len(result.bids) == 2
        assert len(result.asks) == 2
        assert result.best_bid == 1.08500
        assert result.best_ask == 1.08520
        assert result.spread == 0.00020
        assert result.bid_depth == 2
        assert result.ask_depth == 2

    @pytest.mark.asyncio
    async def test_unsubscribe(self, service, mock_audit):
        await service.market_book_subscribe("EURUSD")
        assert "EURUSD" in service._subscriptions
        result = await service.market_book_unsubscribe("EURUSD")
        assert result["symbol"] == "EURUSD"
        assert result["released"] is True
        assert "EURUSD" not in service._subscriptions
        assert len(mock_audit.events) == 2

    @pytest.mark.asyncio
    async def test_unsubscribe_not_subscribed(self, service, mock_audit):
        result = await service.market_book_unsubscribe("EURUSD")
        assert result["released"] is True
        assert "EURUSD" not in service._subscriptions


class TestHandlerFunctions:
    @pytest.mark.asyncio
    async def test_handle_subscribe(self, service):
        result = await handle_market_book_subscribe(service, {"symbol": "gbpusd"})
        assert result["symbol"] == "GBPUSD"
        assert result["subscribed"] is True

    @pytest.mark.asyncio
    async def test_handle_get(self, service):
        await handle_market_book_subscribe(service, {"symbol": "USDJPY"})
        result = await handle_market_book_get(service, {"symbol": "USDJPY"})
        assert result["symbol"] == "USDJPY"
        assert "bids" in result
        assert "asks" in result

    @pytest.mark.asyncio
    async def test_handle_unsubscribe(self, service):
        await handle_market_book_subscribe(service, {"symbol": "XAUUSD"})
        result = await handle_market_book_unsubscribe(service, {"symbol": "XAUUSD"})
        assert result["symbol"] == "XAUUSD"


class TestInputValidation:
    def test_subscribe_input_sanitization(self):
        inp = MarketBookSubscribeInput.model_validate({"symbol": "eurusd"})
        assert inp.symbol == "EURUSD"

    def test_subscribe_input_empty(self):
        with pytest.raises(Exception):  # noqa: B017
            MarketBookSubscribeInput.model_validate({"symbol": ""})

    def test_get_input_sanitization(self):
        inp = MarketBookGetInput.model_validate({"symbol": "xauusd"})
        assert inp.symbol == "XAUUSD"

    def test_unsubscribe_input_sanitization(self):
        inp = MarketBookUnsubscribeInput.model_validate({"symbol": "usdchf"})
        assert inp.symbol == "USDCHF"
