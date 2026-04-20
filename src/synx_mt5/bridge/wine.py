"""Wine Bridge - Bridge wrapper for Wine/Distrobox environments.

Note: For Linux CI without real MT5, use the EA REST bridge (mode="ea_rest")
which connects to a Windows MT5 machine over the network. The EA REST bridge
is the primary cross-platform bridge and works on any OS.

This WineBridge exists for the rare case where you have:
- A Linux host with Wine installed
- MT5 running inside a Wine prefix on the same machine
- pywinauto installed for UI automation

For most Linux use cases, configure mode="ea_rest" instead.
"""

import os
import sys
from typing import Any

import structlog

from synx_mt5.config import BridgeConfig

log = structlog.get_logger(__name__)


class WineBridge:
    """
    Bridge for Wine/Distrobox environments.

    Uses EA REST bridge as the underlying transport when COM is unavailable.
    This is the recommended approach for Linux - configure ea_host/ea_port
    in your config to point to the Windows MT5 machine.
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self._wine_prefix = os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine"))
        self._terminal_path = config.terminal_path or self._detect_wine_terminal_path()

        if sys.platform == "win32":
            from synx_mt5.bridge.python_com import PythonCOMBridge

            log.info("wine_bridge_using_com", terminal_path=self._terminal_path)
            self._delegate: Any = PythonCOMBridge(config)
        else:
            from synx_mt5.bridge.ea_rest import EARestBridge

            log.info(
                "wine_bridge_using_ea_rest",
                wine_prefix=self._wine_prefix,
                ea_host=config.ea_host,
                ea_port=config.ea_port,
                note="Configure ea_host/ea_port for cross-host connectivity",
            )
            self._delegate: Any = EARestBridge(config)

    def _detect_wine_terminal_path(self) -> str:
        """Detect MT5 terminal path in Wine prefix."""
        default_path = os.path.join(
            self._wine_prefix,
            "drive_c/Program Files/MetaTrader 5/terminal64.exe",
        )
        expanded = os.path.expanduser(default_path)
        if os.path.exists(expanded):
            log.info("wine_terminal_detected", path=expanded)
        return expanded

    async def connect(self) -> bool:
        return await self._delegate.connect()

    async def disconnect(self) -> None:
        await self._delegate.disconnect()

    async def is_connected(self) -> bool:
        return await self._delegate.is_connected()

    async def account_info(self) -> dict:
        return await self._delegate.account_info()

    async def terminal_info(self) -> dict:
        return await self._delegate.terminal_info()

    async def symbol_info(self, symbol: str) -> dict | None:
        return await self._delegate.symbol_info(symbol)

    async def symbol_info_tick(self, symbol: str) -> dict | None:
        return await self._delegate.symbol_info_tick(symbol)

    async def symbols_total(self) -> int:
        return await self._delegate.symbols_total()

    async def symbols_get(self, group: str = "*") -> list[dict]:
        return await self._delegate.symbols_get(group)

    async def symbol_select(self, symbol: str, select: bool = True) -> bool:
        return await self._delegate.symbol_select(symbol, select)

    async def copy_rates_from_pos(
        self, symbol: str, timeframe: str, start_pos: int, count: int
    ) -> list[dict]:
        return await self._delegate.copy_rates_from_pos(symbol, timeframe, start_pos, count)

    async def copy_rates_from(
        self, symbol: str, timeframe: str, date_from: str, count: int
    ) -> list[dict]:
        return await self._delegate.copy_rates_from(symbol, timeframe, date_from, count)

    async def copy_rates_range(
        self, symbol: str, timeframe: str, date_from: str, date_to: str
    ) -> list[dict]:
        return await self._delegate.copy_rates_range(symbol, timeframe, date_from, date_to)

    async def copy_ticks_from(
        self, symbol: str, date_from: str, count: int, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict]:
        return await self._delegate.copy_ticks_from(symbol, date_from, count, flags)

    async def copy_ticks_range(
        self, symbol: str, date_from: str, date_to: str, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict]:
        return await self._delegate.copy_ticks_range(symbol, date_from, date_to, flags)

    async def positions_total(self) -> int:
        return await self._delegate.positions_total()

    async def positions_get(self, symbol: str = "", ticket: int = 0) -> list[dict]:
        return await self._delegate.positions_get(symbol, ticket)

    async def orders_total(self) -> int:
        return await self._delegate.orders_total()

    async def orders_get(self, symbol: str = "", ticket: int = 0) -> list[dict]:
        return await self._delegate.orders_get(symbol, ticket)

    async def history_orders_total(self, date_from: str, date_to: str) -> int:
        return await self._delegate.history_orders_total(date_from, date_to)

    async def history_orders_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict]:
        return await self._delegate.history_orders_get(date_from, date_to, symbol)

    async def history_deals_total(self, date_from: str, date_to: str) -> int:
        return await self._delegate.history_deals_total(date_from, date_to)

    async def history_deals_get(self, date_from: str, date_to: str, symbol: str = "") -> list[dict]:
        return await self._delegate.history_deals_get(date_from, date_to, symbol)

    async def order_calc_margin(
        self, order_type: str, symbol: str, volume: float, price: float
    ) -> dict | None:
        return await self._delegate.order_calc_margin(order_type, symbol, volume, price)

    async def order_calc_profit(
        self, order_type: str, symbol: str, volume: float, price_open: float, price_close: float
    ) -> dict | None:
        return await self._delegate.order_calc_profit(
            order_type, symbol, volume, price_open, price_close
        )

    async def order_check(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0,
        tp: float = 0,
    ) -> dict:
        return await self._delegate.order_check(symbol, order_type, volume, price, sl, tp)

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
    ) -> dict:
        return await self._delegate.order_send(
            symbol, order_type, volume, price, sl, tp, magic, comment
        )

    async def position_close(self, ticket: int, volume: float = 0, deviation: int = 20) -> dict:
        return await self._delegate.position_close(ticket, volume, deviation)

    async def position_modify(self, ticket: int, sl: float, tp: float) -> dict:
        return await self._delegate.position_modify(ticket, sl, tp)

    async def order_modify(self, ticket: int, price: float, sl: float, tp: float) -> dict:
        return await self._delegate.order_modify(ticket, price, sl, tp)

    async def order_cancel(self, ticket: int) -> dict:
        return await self._delegate.order_cancel(ticket)

    async def market_book_add(self, symbol: str) -> bool:
        return await self._delegate.market_book_add(symbol)

    async def market_book_get(self, symbol: str) -> list[dict] | None:
        return await self._delegate.market_book_get(symbol)

    async def market_book_release(self, symbol: str) -> bool:
        return await self._delegate.market_book_release(symbol)
