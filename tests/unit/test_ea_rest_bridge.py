"""Unit tests for EA REST bridge module."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from synx_mt5.bridge.ea_rest import EARestBridge
from synx_mt5.config import BridgeConfig


class TestEARestBridge:
    """Test EARestBridge class."""

    @pytest.fixture
    def config(self):
        """Create bridge config."""
        return BridgeConfig(
            ea_host="localhost",
            ea_port=8888,
            ea_timeout_seconds=30,
            ea_api_key="test_key",
        )

    @pytest.fixture
    def bridge(self, config):
        """Create EA REST bridge."""
        return EARestBridge(config=config)

    def test_init(self, config):
        """Test bridge init."""
        bridge = EARestBridge(config=config)
        assert bridge.base_url == "http://localhost:8888"
        assert bridge.timeout == 30
        assert bridge._connected is False

    def test_init_no_api_key(self):
        """Test bridge init without API key."""
        config = BridgeConfig(ea_host="localhost", ea_port=8888)
        bridge = EARestBridge(config=config)
        assert bridge.config.ea_api_key is None

    def test_get_client(self, bridge):
        """Test _get_client creates client."""
        client = bridge._get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)

    def test_get_client_reuses(self, bridge):
        """Test _get_client reuses existing client."""
        client1 = bridge._get_client()
        client2 = bridge._get_client()
        assert client1 is client2


class TestEARestBridgeConnect:
    """Test connect/disconnect methods."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_connect_success(self, config):
        """Test connect with successful health check."""
        bridge = EARestBridge(config=config)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(bridge, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await bridge.connect()
            assert result is True
            assert bridge._connected is True

    @pytest.mark.asyncio
    async def test_connect_failure(self, config):
        """Test connect with failed health check."""
        bridge = EARestBridge(config=config)

        with patch.object(bridge, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_get_client.return_value = mock_client

            result = await bridge.connect()
            assert result is False
            assert bridge._connected is False


class TestEARestBridgeGet:
    """Test _get method."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_get_success(self, config):
        """Test _get with success response."""
        bridge = EARestBridge(config=config)

        with patch.object(bridge, "_get_client") as mock_get_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value={"key": "value"})
            mock_response.raise_for_status = MagicMock()

            async def mock_get(*args, **kwargs):
                return mock_response

            mock_client = MagicMock()
            mock_client.get = mock_get
            mock_get_client.return_value = mock_client

            result = await bridge._get("/test")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_raises_on_error(self, config):
        """Test _get raises on HTTP error."""
        bridge = EARestBridge(config=config)

        with patch.object(bridge, "_get_client") as mock_get_client:
            mock_response = MagicMock()
            mock_response.status_code = 404

            http_error = httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=mock_response
            )

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=http_error)
            mock_get_client.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await bridge._get("/test")


class TestEARestBridgePost:
    """Test _post method."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_post_success(self, config):
        """Test _post with success response."""
        bridge = EARestBridge(config=config)

        with patch.object(bridge, "_get_client") as mock_get_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value={"result": "ok"})
            mock_response.raise_for_status = MagicMock()

            async def mock_post(*args, **kwargs):
                return mock_response

            mock_client = MagicMock()
            mock_client.post = mock_post
            mock_get_client.return_value = mock_client

            result = await bridge._post("/order", {"symbol": "EURUSD"})
            assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_post_raises_on_404(self, config):
        """Test _post raises on 404."""
        bridge = EARestBridge(config=config)

        with patch.object(bridge, "_get_client") as mock_get_client:
            mock_response = MagicMock()
            mock_response.status_code = 404

            http_error = httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=mock_response
            )

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=http_error)
            mock_get_client.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await bridge._post("/order", {"symbol": "EURUSD"})


class TestEARestBridgeAccount:
    """Test account info methods."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_account_info(self, config):
        """Test account_info calls _get."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(return_value={"balance": 10000})

        result = await bridge.account_info()
        bridge._get.assert_called_once_with("/account")
        assert result["balance"] == 10000

    @pytest.mark.asyncio
    async def test_terminal_info(self, config):
        """Test terminal_info calls _get."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(return_value={"build": 3320})

        result = await bridge.terminal_info()
        bridge._get.assert_called_once_with("/terminal")
        assert result["build"] == 3320


class TestEARestBridgeSymbol:
    """Test symbol methods."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_symbol_info_found(self, config):
        """Test symbol_info returns data when found."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(return_value={"symbol": "EURUSD"})

        result = await bridge.symbol_info("EURUSD")
        assert result == {"symbol": "EURUSD"}

    @pytest.mark.asyncio
    async def test_symbol_info_not_found(self, config):
        """Test symbol_info returns None on 404."""
        bridge = EARestBridge(config=config)

        async def raise_404(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 404
            raise httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)

        bridge._get = AsyncMock(side_effect=raise_404)

        result = await bridge.symbol_info("INVALID")
        assert result is None

    @pytest.mark.asyncio
    async def test_symbol_info_tick(self, config):
        """Test symbol_info_tick."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(return_value={"ask": 1.08550, "bid": 1.08500})

        result = await bridge.symbol_info_tick("EURUSD")
        assert result["ask"] == 1.08550


class TestEARestBridgePositions:
    """Test positions and orders methods."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_positions_total(self, config):
        """Test positions_total."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(return_value={"positions": [{}, {}, {}]})

        result = await bridge.positions_total()
        assert result == 3

    @pytest.mark.asyncio
    async def test_positions_get_all(self, config):
        """Test positions_get with no filter."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(return_value={"positions": [{"ticket": 1}, {"ticket": 2}]})

        result = await bridge.positions_get()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_positions_get_by_symbol(self, config):
        """Test positions_get by symbol."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(
            return_value={
                "positions": [
                    {"ticket": 1, "symbol": "EURUSD"},
                    {"ticket": 2, "symbol": "GBPUSD"},
                    {"ticket": 3, "symbol": "EURUSD"},
                ]
            }
        )

        result = await bridge.positions_get(symbol="EURUSD")
        assert len(result) == 2


class TestEARestBridgeEAChart:
    """Test EA chart methods."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_ea_chart_list(self, config):
        """Test ea_chart_list."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(return_value=[{"id": 1}, {"id": 2}])

        result = await bridge.ea_chart_list()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_ea_chart_open(self, config):
        """Test ea_chart_open."""
        bridge = EARestBridge(config=config)
        bridge._post = AsyncMock(return_value={"id": 123})

        result = await bridge.ea_chart_open("EURUSD", "H1")
        bridge._post.assert_called_once()
        assert result["id"] == 123

    @pytest.mark.asyncio
    async def test_ea_chart_close(self, config):
        """Test ea_chart_close."""
        bridge = EARestBridge(config=config)
        bridge._post = AsyncMock(return_value={"closed": True})

        await bridge.ea_chart_close(123)
        bridge._post.assert_called_once_with("/charts/123/close", {})

    @pytest.mark.asyncio
    async def test_ea_chart_screenshot(self, config):
        """Test ea_chart_screenshot."""
        bridge = EARestBridge(config=config)
        bridge._post = AsyncMock(return_value={"image": "base64data"})

        await bridge.ea_chart_screenshot(123, 800, 600, True)
        bridge._post.assert_called_once()

    @pytest.mark.asyncio
    async def test_ea_chart_set_symbol_timeframe(self, config):
        """Test ea_chart_set_symbol_timeframe."""
        bridge = EARestBridge(config=config)
        bridge._post = AsyncMock()

        await bridge.ea_chart_set_symbol_timeframe(123, "EURUSD", "H1")
        bridge._post.assert_called_once()

    @pytest.mark.asyncio
    async def test_ea_chart_indicator_list(self, config):
        """Test ea_chart_indicator_list."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(return_value=[{"name": "RSI"}])

        await bridge.ea_chart_indicator_list(123)
        bridge._get.assert_called_once()

    @pytest.mark.asyncio
    async def test_ea_chart_navigate(self, config):
        """Test ea_chart_navigate."""
        bridge = EARestBridge(config=config)
        bridge._post = AsyncMock()

        await bridge.ea_chart_navigate(123, "end", 100)
        bridge._post.assert_called_once()


class TestEARestBridgeScripts:
    """Test script execution."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_ea_run_script(self, config):
        """Test ea_run_script."""
        bridge = EARestBridge(config=config)
        bridge._post = AsyncMock(return_value={"result": "success"})

        result = await bridge.ea_run_script(123, "my_script", {"param": "value"})
        bridge._post.assert_called_once()
        assert result["result"] == "success"


class TestEARestBridgeMarketBook:
    """Test market book methods."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_market_book_add(self, config):
        """Test market_book_add."""
        bridge = EARestBridge(config=config)
        bridge._post = AsyncMock(return_value={"subscribed": True})

        result = await bridge.market_book_add("EURUSD")
        assert result is True

    @pytest.mark.asyncio
    async def test_market_book_get(self, config):
        """Test market_book_get."""
        bridge = EARestBridge(config=config)
        bridge._get = AsyncMock(return_value={"entries": [{"price": 1.085}]})

        result = await bridge.market_book_get("EURUSD")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_market_book_release(self, config):
        """Test market_book_release."""
        bridge = EARestBridge(config=config)
        bridge._post = AsyncMock(return_value={"unsubscribed": True})

        result = await bridge.market_book_release("EURUSD")
        assert result is True


class TestEARestBridgeClose:
    """Test close method."""

    @pytest.fixture
    def config(self):
        return BridgeConfig(ea_host="localhost", ea_port=8888)

    @pytest.mark.asyncio
    async def test_close(self, config):
        """Test close closes client."""
        bridge = EARestBridge(config=config)
        client = bridge._get_client()
        client.aclose = AsyncMock()

        await bridge.close()
        assert bridge._client is None
