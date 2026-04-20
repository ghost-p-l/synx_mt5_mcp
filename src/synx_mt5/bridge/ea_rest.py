"""EA REST Bridge - Cross-platform bridge via SYNX_EA HTTP service."""

from typing import Any

import httpx

from synx_mt5.bridge.base import MT5Bridge
from synx_mt5.config import BridgeConfig


class EARestBridge(MT5Bridge):
    """
    Bridge using SYNX_EA REST API.
    Works on any platform where MT5 runs on network-accessible Windows machine.
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.base_url = f"http://{config.ea_host}:{config.ea_port}"
        self.timeout = config.ea_timeout_seconds
        self._connected = False
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.config.ea_api_key}"}
                if self.config.ea_api_key
                else {},
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def connect(self) -> bool:
        """Connect to EA REST service."""
        try:
            client = self._get_client()
            response = await client.get("/health")
            self._connected = response.status_code == 200
            return self._connected
        except Exception:
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from EA REST service."""
        await self.close()
        self._connected = False

    async def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def _get(self, path: str) -> dict[str, Any] | list[Any]:
        """GET request to EA."""
        client = self._get_client()
        response = await client.get(path)
        response.raise_for_status()
        return response.json()

    async def _post(self, path: str, data: dict = None) -> dict[str, Any]:
        """POST request to EA."""
        client = self._get_client()
        response = await client.post(path, json=data or {})
        response.raise_for_status()
        return response.json()

    async def account_info(self) -> dict[str, Any]:
        """Get account info."""
        return await self._get("/account")

    async def terminal_info(self) -> dict[str, Any]:
        """Get terminal info."""
        return await self._get("/terminal")

    async def symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get symbol info."""
        try:
            data = await self._get(f"/symbols/{symbol}")
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def symbol_info_tick(self, symbol: str) -> dict[str, Any] | None:
        """Get current tick."""
        try:
            return await self._get(f"/tick/{symbol}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def symbols_total(self) -> int:
        """Get symbols total."""
        data = await self._get("/symbols")
        return len(data.get("symbols", []))

    async def symbols_get(self, group: str = "*") -> list[dict[str, Any]]:
        """Get symbols by group."""
        data = await self._get("/symbols")
        return data.get("symbols", [])

    async def symbol_select(self, symbol: str, select: bool = True) -> bool:
        """Select symbol (not directly supported, placeholder)."""
        return True

    async def copy_rates_from_pos(
        self, symbol: str, timeframe: str, start_pos: int, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates from position."""
        data = await self._get(f"/rates/{symbol}/{timeframe}/{count}")
        return data if isinstance(data, list) else []  # type: ignore[return-value]

    async def copy_rates_from(
        self, symbol: str, timeframe: str, date_from: str, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates from datetime."""
        data = await self._get(f"/rates/{symbol}/{timeframe}/{count}")
        return data if isinstance(data, list) else []  # type: ignore[return-value]

    async def copy_rates_range(
        self, symbol: str, timeframe: str, date_from: str, date_to: str
    ) -> list[dict[str, Any]]:
        """Copy rates in range."""
        data = await self._get(f"/rates/{symbol}/{timeframe}/{date_from}")
        return data if isinstance(data, list) else []  # type: ignore[return-value]

    async def copy_ticks_from(
        self, symbol: str, date_from: str, count: int, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks from datetime."""
        data = await self._get(f"/ticks/{symbol}/{count}")
        return data if isinstance(data, list) else []  # type: ignore[return-value]

    async def copy_ticks_range(
        self, symbol: str, date_from: str, date_to: str, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks in range."""
        data = await self._get(f"/ticks/{symbol}/{date_from}")
        return data if isinstance(data, list) else []  # type: ignore[return-value]

    async def positions_total(self) -> int:
        """Get positions total."""
        data = await self._get("/positions")
        return len(data.get("positions", []))

    async def positions_get(self, symbol: str = "", ticket: int = 0) -> list[dict[str, Any]]:
        """Get positions."""
        data = await self._get("/positions")
        positions = data.get("positions", [])
        if ticket:
            return [p for p in positions if p.get("ticket") == ticket]
        if symbol:
            return [p for p in positions if p.get("symbol") == symbol]
        return positions

    async def orders_total(self) -> int:
        """Get orders total."""
        data = await self._get("/orders")
        return len(data.get("orders", []))

    async def orders_get(self, symbol: str = "", ticket: int = 0) -> list[dict[str, Any]]:
        """Get orders."""
        data = await self._get("/orders")
        orders = data.get("orders", [])
        if ticket:
            return [o for o in orders if o.get("ticket") == ticket]
        if symbol:
            return [o for o in orders if o.get("symbol") == symbol]
        return orders

    async def history_orders_total(self, date_from: str, date_to: str) -> int:
        """Get history orders total."""
        return 0

    async def history_orders_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get history orders."""
        return []

    async def history_deals_total(self, date_from: str, date_to: str) -> int:
        """Get history deals total."""
        return 0

    async def history_deals_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get history deals."""
        return []

    async def order_calc_margin(
        self, order_type: str, symbol: str, volume: float, price: float
    ) -> dict[str, Any] | None:
        """Calculate margin."""
        try:
            return await self._post(
                "/calc/margin",
                {
                    "order_type": order_type,
                    "symbol": symbol,
                    "volume": volume,
                    "price": price,
                },
            )
        except Exception:
            return None

    async def order_calc_profit(
        self, order_type: str, symbol: str, volume: float, price_open: float, price_close: float
    ) -> dict[str, Any] | None:
        """Calculate profit."""
        try:
            return await self._post(
                "/calc/profit",
                {
                    "order_type": order_type,
                    "symbol": symbol,
                    "volume": volume,
                    "price_open": price_open,
                    "price_close": price_close,
                },
            )
        except Exception:
            return None

    async def order_check(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0,
        tp: float = 0,
    ) -> dict[str, Any]:
        """Check order."""
        return await self._post(
            "/order/check",
            {
                "symbol": symbol,
                "order_type": order_type,
                "volume": volume,
                "price": price,
                "sl": sl,
                "tp": tp,
            },
        )

    async def order_send(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0,
        tp: float = 0,
        magic: int = 0,
        comment: str = "",
    ) -> dict[str, Any]:
        """Send order."""
        return await self._post(
            "/order",
            {
                "symbol": symbol,
                "order_type": order_type,
                "volume": volume,
                "price": price,
                "sl": sl,
                "tp": tp,
                "magic": magic,
                "comment": comment,
            },
        )

    async def position_close(
        self, ticket: int, volume: float = 0, deviation: int = 20
    ) -> dict[str, Any]:
        """Close position."""
        return await self._post(
            f"/position/{ticket}/close",
            {
                "volume": volume,
                "deviation": deviation,
            },
        )

    async def position_modify(self, ticket: int, sl: float, tp: float) -> dict[str, Any]:
        """Modify position."""
        return await self._post(
            f"/position/{ticket}/modify",
            {
                "sl": sl,
                "tp": tp,
            },
        )

    async def order_modify(self, ticket: int, price: float, sl: float, tp: float) -> dict[str, Any]:
        """Modify pending order."""
        return await self._post(
            f"/order/{ticket}",
            {
                "price": price,
                "sl": sl,
                "tp": tp,
            },
        )

    async def order_cancel(self, ticket: int) -> dict[str, Any]:
        """Cancel pending order."""
        return await self._post(f"/order/{ticket}/cancel", {})

    async def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market book."""
        try:
            await self._post(f"/dom/{symbol}/subscribe", {})
            return True
        except Exception:
            return False

    async def market_book_get(self, symbol: str) -> list[dict[str, Any]] | None:
        """Get market book."""
        try:
            data = await self._get(f"/dom/{symbol}")
            return data.get("entries", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def market_book_release(self, symbol: str) -> bool:
        """Release market book subscription."""
        try:
            await self._post(f"/dom/{symbol}/unsubscribe", {})
            return True
        except Exception:
            return False

    async def ea_chart_list(self) -> list[dict[str, Any]]:
        """List all open charts."""
        return await self._get("/charts")

    async def ea_chart_open(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """Open a new chart."""
        return await self._post("/charts", {"symbol": symbol, "timeframe": timeframe})

    async def ea_chart_close(self, chart_id: int) -> dict[str, Any]:
        """Close a chart by ID."""
        return await self._post(f"/charts/{chart_id}/close", {})

    async def ea_chart_screenshot(
        self, chart_id: int, width: int, height: int, align_to_right: bool
    ) -> dict[str, Any]:
        """Capture chart as PNG image."""
        return await self._post(
            f"/charts/{chart_id}/screenshot",
            {"width": width, "height": height, "align_to_right": align_to_right},
        )

    async def ea_chart_set_symbol_timeframe(
        self, chart_id: int, symbol: str | None, timeframe: str | None
    ) -> None:
        """Change chart symbol and/or timeframe."""
        data: dict[str, str] = {}
        if symbol is not None:
            data["symbol"] = symbol
        if timeframe is not None:
            data["timeframe"] = timeframe
        await self._post(f"/charts/{chart_id}", data)

    async def ea_chart_apply_template(self, chart_id: int, template_name: str) -> dict[str, Any]:
        """Apply a .tpl template to a chart."""
        return await self._post(f"/charts/{chart_id}/template", {"template": template_name})

    async def ea_chart_save_template(self, chart_id: int, template_name: str) -> dict[str, Any]:
        """Save chart as a .tpl template."""
        return await self._post(f"/charts/{chart_id}/save_template", {"template": template_name})

    async def ea_chart_navigate(self, chart_id: int, position: str, shift: int) -> dict[str, Any]:
        """Navigate chart scroll position."""
        return await self._post(
            f"/charts/{chart_id}/navigate",
            {"position": position, "shift": shift},
        )

    async def ea_chart_indicator_add(
        self,
        chart_id: int,
        indicator_path: str,
        window: int,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Add an indicator to a chart."""
        return await self._post(
            f"/charts/{chart_id}/indicators",
            {
                "indicator_path": indicator_path,
                "window": window,
                "parameters": parameters,
            },
        )

    async def ea_chart_indicator_list(
        self, chart_id: int, window: int | None = None
    ) -> list[dict[str, Any]]:
        """List indicators on a chart."""
        path = f"/charts/{chart_id}/indicators"
        if window is not None:
            path += f"?window={window}"
        return await self._get(path)

    async def ea_run_script(
        self, chart_id: int, script_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an MQL5 script on a chart."""
        return await self._post(
            "/scripts/run",
            {
                "chart_id": chart_id,
                "script_name": script_name,
                "parameters": parameters,
            },
        )
