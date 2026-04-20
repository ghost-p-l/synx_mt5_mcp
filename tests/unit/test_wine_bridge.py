"""Tests for WineBridge delegation logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synx_mt5.bridge.wine import WineBridge
from synx_mt5.config import BridgeConfig


@pytest.fixture
def bridge_config():
    return BridgeConfig(
        mode="ea_rest",
        ea_host="127.0.0.1",
        ea_port=18765,
    )


class TestWineBridgeLinux:
    @patch("sys.platform", "linux")
    @patch("synx_mt5.bridge.ea_rest.EARestBridge")
    def test_init_linux_delegates_to_ea_rest(self, mock_ea_rest, bridge_config):
        mock_instance = MagicMock()
        mock_ea_rest.return_value = mock_instance

        wb = WineBridge(bridge_config)

        mock_ea_rest.assert_called_once_with(bridge_config)
        assert wb._delegate is mock_instance

    @pytest.mark.asyncio
    @patch("sys.platform", "linux")
    @patch("synx_mt5.bridge.ea_rest.EARestBridge")
    async def test_connect_delegates(self, mock_ea_rest, bridge_config):
        mock_instance = AsyncMock()
        mock_instance.connect = AsyncMock(return_value=True)
        mock_ea_rest.return_value = mock_instance

        wb = WineBridge(bridge_config)
        result = await wb.connect()

        mock_instance.connect.assert_called_once()
        assert result is True

    @pytest.mark.asyncio
    @patch("sys.platform", "linux")
    @patch("synx_mt5.bridge.ea_rest.EARestBridge")
    async def test_disconnect_delegates(self, mock_ea_rest, bridge_config):
        mock_instance = AsyncMock()
        mock_instance.disconnect = AsyncMock()
        mock_ea_rest.return_value = mock_instance

        wb = WineBridge(bridge_config)
        await wb.disconnect()

        mock_instance.disconnect.assert_called_once()

    @pytest.mark.asyncio
    @patch("sys.platform", "linux")
    @patch("synx_mt5.bridge.ea_rest.EARestBridge")
    async def test_account_info_delegates(self, mock_ea_rest, bridge_config):
        mock_instance = AsyncMock()
        mock_instance.account_info = AsyncMock(return_value={"login": 12345})
        mock_ea_rest.return_value = mock_instance

        wb = WineBridge(bridge_config)
        result = await wb.account_info()

        mock_instance.account_info.assert_called_once()
        assert result == {"login": 12345}

    @pytest.mark.asyncio
    @patch("sys.platform", "linux")
    @patch("synx_mt5.bridge.ea_rest.EARestBridge")
    async def test_terminal_info_delegates(self, mock_ea_rest, bridge_config):
        mock_instance = AsyncMock()
        mock_instance.terminal_info = AsyncMock(return_value={"terminal": "MetaTrader 5"})
        mock_ea_rest.return_value = mock_instance

        wb = WineBridge(bridge_config)
        result = await wb.terminal_info()

        mock_instance.terminal_info.assert_called_once()
        assert result == {"terminal": "MetaTrader 5"}


class TestWineBridgeWindows:
    pass


class TestWineBridgeDelegation:
    @pytest.mark.asyncio
    @patch("sys.platform", "linux")
    @patch("synx_mt5.bridge.ea_rest.EARestBridge")
    async def test_positions_get_delegates(self, mock_ea_rest, bridge_config):
        mock_instance = AsyncMock()
        mock_instance.positions_get = AsyncMock(return_value=[{"ticket": 1}])
        mock_ea_rest.return_value = mock_instance

        wb = WineBridge(bridge_config)
        result = await wb.positions_get(symbol="EURUSD")

        mock_instance.positions_get.assert_called_once_with("EURUSD", 0)
        assert result == [{"ticket": 1}]

    @pytest.mark.asyncio
    @patch("sys.platform", "linux")
    @patch("synx_mt5.bridge.ea_rest.EARestBridge")
    async def test_orders_get_delegates(self, mock_ea_rest, bridge_config):
        mock_instance = AsyncMock()
        mock_instance.orders_get = AsyncMock(return_value=[{"ticket": 2}])
        mock_ea_rest.return_value = mock_instance

        wb = WineBridge(bridge_config)
        result = await wb.orders_get(symbol="GBPUSD")

        mock_instance.orders_get.assert_called_once_with("GBPUSD", 0)
        assert result == [{"ticket": 2}]

    @pytest.mark.asyncio
    @patch("sys.platform", "linux")
    @patch("synx_mt5.bridge.ea_rest.EARestBridge")
    async def test_history_orders_get_delegates(self, mock_ea_rest, bridge_config):
        mock_instance = AsyncMock()
        mock_instance.history_orders_get = AsyncMock(return_value=[{"ticket": 3}])
        mock_ea_rest.return_value = mock_instance

        wb = WineBridge(bridge_config)
        result = await wb.history_orders_get("2024-01-01", "2024-01-31", "EURUSD")

        mock_instance.history_orders_get.assert_called_once_with(
            "2024-01-01", "2024-01-31", "EURUSD"
        )
        assert result == [{"ticket": 3}]

    @pytest.mark.asyncio
    @patch("sys.platform", "linux")
    @patch("synx_mt5.bridge.ea_rest.EARestBridge")
    async def test_order_send_delegates(self, mock_ea_rest, bridge_config):
        mock_instance = AsyncMock()
        mock_instance.order_send = AsyncMock(return_value={"order": 123, "retcode": 10009})
        mock_ea_rest.return_value = mock_instance

        wb = WineBridge(bridge_config)
        result = await wb.order_send(
            symbol="EURUSD",
            order_type="buy",
            volume=0.01,
            price=1.1000,
        )

        mock_instance.order_send.assert_called_once()
        assert result == {"order": 123, "retcode": 10009}
