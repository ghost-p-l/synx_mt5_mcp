"""Integration tests with mock MT5 bridge."""


import pytest


class MockMT5Bridge:
    """Mock MT5 bridge for testing."""

    def __init__(self):
        self._connected = False
        self.symbols = {
            "EURUSD": {"trade_mode": 1, "volume_min": 0.01, "volume_max": 100},
            "GBPUSD": {"trade_mode": 1, "volume_min": 0.01, "volume_max": 100},
        }

    async def connect(self):
        self._connected = True
        return True

    async def disconnect(self):
        self._connected = False

    async def is_connected(self):
        return self._connected

    async def account_info(self):
        return {
            "login": 12345,
            "balance": 10000,
            "equity": 10500,
            "trade_mode": 0,
        }

    async def symbol_info(self, symbol):
        return self.symbols.get(symbol)

    async def symbol_info_tick(self, symbol):
        return {"bid": 1.08500, "ask": 1.08520, "volume": 1000}


class TestBridgeIntegration:
    """Integration tests with mock bridge."""

    @pytest.fixture
    def bridge(self):
        return MockMT5Bridge()

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, bridge):
        """Test connection lifecycle."""
        assert await bridge.is_connected() is False
        await bridge.connect()
        assert await bridge.is_connected() is True
        await bridge.disconnect()
        assert await bridge.is_connected() is False

    @pytest.mark.asyncio
    async def test_account_info(self, bridge):
        """Test account info retrieval."""
        await bridge.connect()
        info = await bridge.account_info()
        assert info["login"] == 12345
        assert info["balance"] == 10000

    @pytest.mark.asyncio
    async def test_symbol_info(self, bridge):
        """Test symbol info."""
        info = await bridge.symbol_info("EURUSD")
        assert info["trade_mode"] == 1
