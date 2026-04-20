"""Python COM Bridge - Native MT5 Python API bridge for Windows."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import MetaTrader5 as mt5

from synx_mt5.bridge.base import MT5Bridge
from synx_mt5.config import BridgeConfig
from synx_mt5.security.secrets import CredentialKey, load_credential


class PythonCOMBridge(MT5Bridge):
    """
    Bridge using official MetaTrader5 Python package.
    Works only on Windows via COM/IPC.
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mt5-bridge")
        self._connected = False
        self._ea = None          # SYNXEABridge, lazily initialised
        self._terminal_data_path = ""  # Populated after connect()

    async def connect(self) -> bool:
        """Connect to MT5 terminal."""
        login = load_credential(CredentialKey.LOGIN)
        password = load_credential(CredentialKey.PASSWORD)
        server = load_credential(CredentialKey.SERVER)

        if not all([login, password, server]):
            raise RuntimeError("MT5 credentials not found. Run `synx-mt5 setup` first.")

        path = self.config.terminal_path

        def _init():
            kwargs = {"timeout": 60000}
            if path:
                kwargs["path"] = path
            return mt5.initialize(**kwargs)

        loop = asyncio.get_running_loop()
        initialized = await loop.run_in_executor(self._executor, _init)
        if not initialized:
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

        def _login():
            _login_str = login.value
            _password_str = password.value
            _server_str = server.value
            return mt5.login(int(_login_str), password=_password_str, server=_server_str)

        logged_in = await loop.run_in_executor(self._executor, _login)
        self._connected = logged_in

        if logged_in:
            def _data_path():
                info = mt5.terminal_info()
                return getattr(info, "data_path", "") if info else ""
            self._terminal_data_path = await loop.run_in_executor(self._executor, _data_path)

        return logged_in

    async def disconnect(self) -> None:
        """Disconnect from MT5."""
        await asyncio.get_running_loop().run_in_executor(self._executor, mt5.shutdown)
        self._connected = False
        self._ea = None

    async def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    def _run(self, fn, *args, **kwargs):
        """Run MT5 function in executor."""
        return asyncio.get_running_loop().run_in_executor(self._executor, lambda: fn(*args, **kwargs))

    def _dict_from_mt5(self, obj) -> dict[str, Any]:
        """Convert MT5 struct to dict."""
        if obj is None:
            return {}
        return {
            "login": getattr(obj, "login", 0),
            "trade_mode": getattr(obj, "trade_mode", 0),
            "balance": getattr(obj, "balance", 0.0),
            "equity": getattr(obj, "equity", 0.0),
            "margin": getattr(obj, "margin", 0.0),
            "margin_free": getattr(obj, "margin_free", 0.0),
            "margin_level": getattr(obj, "margin_level", 0.0),
            "profit": getattr(obj, "profit", 0.0),
            "credit": getattr(obj, "credit", 0.0),
            "commission": getattr(obj, "commission", 0.0),
            "swap": getattr(obj, "swap", 0.0),
            "currency": getattr(obj, "currency", ""),
            "server": getattr(obj, "server", ""),
        }

    async def account_info(self) -> dict[str, Any]:
        """Get account info."""
        info = await self._run(mt5.account_info)
        return self._dict_from_mt5(info)

    async def terminal_info(self) -> dict[str, Any]:
        """Get terminal info."""
        info = await self._run(mt5.terminal_info)
        if info is None:
            return {}
        return {
            "community_account": getattr(info, "community_account", ""),
            "community_balance": getattr(info, "community_balance", 0.0),
            "connected": getattr(info, "connected", False),
            "trade_allowed": getattr(info, "trade_allowed", False),
            "trade_expert": getattr(info, "trade_expert", False),
            "dlls_allowed": getattr(info, "dlls_allowed", False),
            "mqid": getattr(info, "mqid", False),
            "ping_last": getattr(info, "ping_last", 0),
            "company": getattr(info, "company", ""),
            "name": getattr(info, "name", ""),
            "language": getattr(info, "language", ""),
            "path": getattr(info, "path", ""),
            "data_path": getattr(info, "data_path", ""),
            "version": getattr(info, "version", ""),
        }

    async def symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get symbol info."""
        info = await self._run(mt5.symbol_info, symbol)
        if info is None:
            return None
        return {
            "name": getattr(info, "name", symbol),
            "description": getattr(info, "description", ""),
            "path": getattr(info, "path", ""),
            "digits": getattr(info, "digits", 0),
            "trade_mode": getattr(info, "trade_mode", 0),
            "bid": getattr(info, "bid", 0.0),
            "bid_high": getattr(info, "bid_high", 0.0),
            "bid_low": getattr(info, "bid_low", 0.0),
            "ask": getattr(info, "ask", 0.0),
            "ask_high": getattr(info, "ask_high", 0.0),
            "ask_low": getattr(info, "ask_low", 0.0),
            "last": getattr(info, "last", 0.0),
            "volume": getattr(info, "volume", 0.0),
            "volume_high": getattr(info, "volume_high", 0.0),
            "volume_low": getattr(info, "volume_low", 0.0),
            "spread": getattr(info, "spread", 0),
            "spread_raw": getattr(info, "spread_raw", 0),
            "trade_tick_value": getattr(info, "trade_tick_value", 0.0),
            "trade_tick_size": getattr(info, "trade_tick_size", 0.0),
            "trade_contract_size": getattr(info, "trade_contract_size", 0.0),
            "volume_min": getattr(info, "volume_min", 0.0),
            "volume_max": getattr(info, "volume_max", 0.0),
            "volume_step": getattr(info, "volume_step", 0.0),
            "point": getattr(info, "point", 0.0),
        }

    async def symbol_info_tick(self, symbol: str) -> dict[str, Any] | None:
        """Get current tick."""
        tick = await self._run(mt5.symbol_info_tick, symbol)
        if tick is None:
            return None
        return {
            "bid": getattr(tick, "bid", 0.0),
            "ask": getattr(tick, "ask", 0.0),
            "last": getattr(tick, "last", 0.0),
            "volume": getattr(tick, "volume", 0),
            "time": getattr(tick, "time", 0),
            "flags": getattr(tick, "flags", 0),
        }

    async def symbols_total(self) -> int:
        """Get symbols total."""
        return await self._run(mt5.symbols_total)

    async def symbols_get(self, group: str = "*") -> list[dict[str, Any]]:
        """Get symbols by group."""
        symbols = await self._run(mt5.symbols_get, group)
        if symbols is None:
            return []
        return [{"name": s.name} for s in symbols]

    async def symbol_select(self, symbol: str, select: bool = True) -> bool:
        """Select/deselect symbol."""
        return await self._run(mt5.symbol_select, symbol, select)

    def _resolve_timeframe(self, timeframe: str) -> int:
        """Resolve timeframe string to MT5 constant."""
        tf = getattr(mt5, f"TIMEFRAME_{timeframe}", None) or getattr(mt5, f"PERIOD_{timeframe}", None)
        if tf is None:
            raise ValueError(f"Unknown timeframe: {timeframe}")
        return tf

    async def copy_rates_from_pos(
        self, symbol: str, timeframe: str, start_pos: int, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates from position."""
        tf = self._resolve_timeframe(timeframe)
        rates = await self._run(mt5.copy_rates_from_pos, symbol, tf, start_pos, count)
        if rates is None:
            return []
        return [
            {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "tick_volume": int(r["tick_volume"]),
                "spread": int(r["spread"]),
                "real_volume": int(r["real_volume"]),
            }
            for r in rates
        ]

    async def copy_rates_from(
        self, symbol: str, timeframe: str, date_from: str, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates from datetime."""
        from datetime import datetime

        tf = self._resolve_timeframe(timeframe)
        dt = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        rates = await self._run(mt5.copy_rates_from, symbol, tf, dt, count)
        if rates is None:
            return []
        return [
            {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "tick_volume": int(r["tick_volume"]),
                "spread": int(r["spread"]),
                "real_volume": int(r["real_volume"]),
            }
            for r in rates
        ]

    async def copy_rates_range(
        self, symbol: str, timeframe: str, date_from: str, date_to: str
    ) -> list[dict[str, Any]]:
        """Copy rates in range."""
        from datetime import datetime

        tf = self._resolve_timeframe(timeframe)
        dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        rates = await self._run(mt5.copy_rates_range, symbol, tf, dt_from, dt_to)
        if rates is None:
            return []
        return [
            {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "tick_volume": int(r["tick_volume"]),
                "spread": int(r["spread"]),
                "real_volume": int(r["real_volume"]),
            }
            for r in rates
        ]

    async def copy_ticks_from(
        self, symbol: str, date_from: str, count: int, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks from datetime."""
        from datetime import datetime

        dt = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        fl = getattr(mt5, flags, mt5.COPY_TICKS_ALL)
        ticks = await self._run(mt5.copy_ticks_from, symbol, dt, count, fl)
        if ticks is None:
            return []
        return [
            {
                "time": int(t["time"]),
                "bid": float(t["bid"]),
                "ask": float(t["ask"]),
                "last": float(t["last"]),
                "volume": int(t["volume"]),
                "time_msc": int(t["time_msc"]),
                "flags": int(t["flags"]),
            }
            for t in ticks
        ]

    async def copy_ticks_range(
        self, symbol: str, date_from: str, date_to: str, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks in range."""
        from datetime import datetime

        dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        fl = getattr(mt5, flags, mt5.COPY_TICKS_ALL)
        ticks = await self._run(mt5.copy_ticks_range, symbol, dt_from, dt_to, fl)
        if ticks is None:
            return []
        return [
            {
                "time": int(t["time"]),
                "bid": float(t["bid"]),
                "ask": float(t["ask"]),
                "last": float(t["last"]),
                "volume": int(t["volume"]),
                "time_msc": int(t["time_msc"]),
                "flags": int(t["flags"]),
            }
            for t in ticks
        ]

    async def positions_total(self) -> int:
        """Get positions total."""
        return await self._run(mt5.positions_total)

    async def positions_get(self, symbol: str = "", ticket: int = 0) -> list[dict[str, Any]]:
        """Get positions."""
        def _to_dict(p):
            return p._asdict() if hasattr(p, "_asdict") else dict(p)

        if ticket:
            pos = await self._run(mt5.positions_get, ticket=ticket)
            return [_to_dict(p) for p in pos] if pos else []
        if symbol:
            pos = await self._run(mt5.positions_get, symbol=symbol)
            return [_to_dict(p) for p in pos] if pos else []
        positions = await self._run(mt5.positions_get)
        return [_to_dict(p) for p in positions] if positions else []

    async def orders_total(self) -> int:
        """Get orders total."""
        return await self._run(mt5.orders_total)

    async def orders_get(self, symbol: str = "", ticket: int = 0) -> list[dict[str, Any]]:
        """Get orders."""
        def _to_dict(o):
            return o._asdict() if hasattr(o, "_asdict") else dict(o)

        if ticket:
            order = await self._run(mt5.orders_get, ticket=ticket)
            return [_to_dict(o) for o in order] if order else []
        if symbol:
            orders = await self._run(mt5.orders_get, symbol=symbol)
            return [_to_dict(o) for o in orders] if orders else []
        orders = await self._run(mt5.orders_get)
        return [_to_dict(o) for o in orders] if orders else []

    async def history_orders_total(self, date_from: str, date_to: str) -> int:
        """Get history orders total."""
        from datetime import datetime

        dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        return await self._run(mt5.history_orders_total, dt_from, dt_to)

    async def history_orders_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get history orders."""
        from datetime import datetime

        def _to_dict(o):
            return o._asdict() if hasattr(o, "_asdict") else dict(o)

        dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        orders = await self._run(
            mt5.history_orders_get, dt_from, dt_to, symbol=symbol if symbol else None
        )
        return [_to_dict(o) for o in orders] if orders else []

    async def history_deals_total(self, date_from: str, date_to: str) -> int:
        """Get history deals total."""
        from datetime import datetime

        dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        return await self._run(mt5.history_deals_total, dt_from, dt_to)

    async def history_deals_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get history deals."""
        from datetime import datetime

        def _to_dict(d):
            return d._asdict() if hasattr(d, "_asdict") else dict(d)

        dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        deals = await self._run(
            mt5.history_deals_get, dt_from, dt_to, symbol=symbol if symbol else None
        )
        return [_to_dict(d) for d in deals] if deals else []

    async def order_calc_margin(
        self, order_type: str, symbol: str, volume: float, price: float
    ) -> dict[str, Any] | None:
        """Calculate margin."""
        ot = getattr(mt5, order_type)
        result = await self._run(mt5.order_calc_margin, ot, symbol, volume, price)
        if result is None:
            return None
        return {"margin": result[0], "currency": result[1]}

    async def order_calc_profit(
        self, order_type: str, symbol: str, volume: float, price_open: float, price_close: float
    ) -> dict[str, Any] | None:
        """Calculate profit."""
        ot = getattr(mt5, order_type)
        result = await self._run(mt5.order_calc_profit, ot, symbol, volume, price_open, price_close)
        if result is None:
            return None
        return {"profit": result[0], "currency": result[1]}

    async def order_check(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0,
        tp: float = 0,
    ) -> dict[str, Any]:
        """Check order request."""
        ot = getattr(mt5, order_type)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": ot,
            "price": price,
            "sl": sl,
            "tp": tp,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = await self._run(mt5.order_check, request)
        if result is None:
            return {"retcode": -1, "comment": "Failed"}
        return {
            "retcode": getattr(result, "retcode", -1),
            "balance": getattr(result, "balance", 0.0),
            "equity": getattr(result, "equity", 0.0),
            "profit": getattr(result, "profit", 0.0),
            "margin": getattr(result, "margin", 0.0),
            "margin_free": getattr(result, "margin_free", 0.0),
            "margin_level": getattr(result, "margin_level", 0.0),
            "comment": getattr(result, "comment", ""),
        }

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
        ot = getattr(mt5, order_type)
        is_pending = any(lt in order_type for lt in ["LIMIT", "STOP"])
        action = mt5.TRADE_ACTION_PENDING if is_pending else mt5.TRADE_ACTION_DEAL
        request = {
            "action": action,
            "symbol": symbol,
            "volume": volume,
            "type": ot,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.config.slippage_points,
            "magic": magic,
            "comment": comment or "synx-mt5",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK if not is_pending else mt5.ORDER_FILLING_RETURN,
        }
        result = await self._run(mt5.order_send, **request)
        if result is None:
            return {"retcode": -1, "retcode_description": "Failed"}
        return {
            "retcode": getattr(result, "retcode", -1),
            "retcode_description": getattr(result, "comment", ""),
            "ticket": getattr(result, "order", 0),
            "volume": getattr(result, "volume", 0.0),
            "price": getattr(result, "price", 0.0),
        }

    async def position_close(
        self, ticket: int, volume: float = 0, deviation: int = 20
    ) -> dict[str, Any]:
        """Close position."""
        positions = await self._run(mt5.positions_get, ticket=ticket)
        if not positions:
            return {"retcode": -1, "retcode_description": "Position not found"}
        pos = positions[0]
        pos_type = getattr(pos, "type", 0)
        symbol = getattr(pos, "symbol", "")
        price_info = await self._run(mt5.symbol_info_tick, symbol)
        ask = getattr(price_info, "ask", 0) if pos_type == 0 else getattr(price_info, "bid", 0)
        close_type = mt5.ORDER_TYPE_SELL if pos_type == 0 else mt5.ORDER_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "position": ticket,
            "volume": volume or getattr(pos, "volume", 0.01),
            "type": close_type,
            "price": ask,
            "deviation": deviation,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        result = await self._run(mt5.order_send, **request)
        if result is None:
            return {"retcode": -1, "retcode_description": "Failed"}
        return {
            "retcode": getattr(result, "retcode", -1),
            "retcode_description": getattr(result, "comment", ""),
            "ticket": getattr(result, "order", 0),
        }

    async def position_modify(self, ticket: int, sl: float, tp: float) -> dict[str, Any]:
        """Modify position."""
        # MT5 requires symbol in SLTP request — look it up from the open position
        positions = await self._run(mt5.positions_get, ticket=ticket)
        symbol = ""
        if positions:
            pos = positions[0]
            symbol = getattr(pos, "symbol", "") if hasattr(pos, "symbol") else pos.get("symbol", "")
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": sl,
            "tp": tp,
        }
        result = await self._run(mt5.order_send, **request)
        if result is None:
            err = await self._run(mt5.last_error)
            return {"retcode": -1, "retcode_description": f"order_send None. symbol='{symbol}' last_error={err}"}
        return {"retcode": getattr(result, "retcode", -1), "retcode_description": getattr(result, "comment", "")}

    async def order_modify(self, ticket: int, price: float, sl: float, tp: float) -> dict[str, Any]:
        """Modify pending order."""
        request = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": ticket,
            "price": price,
            "sl": sl,
            "tp": tp,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        result = await self._run(mt5.order_send, **request)
        if result is None:
            return {"retcode": -1}
        return {"retcode": getattr(result, "retcode", -1)}

    async def order_cancel(self, ticket: int) -> dict[str, Any]:
        """Cancel pending order."""
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        }
        result = await self._run(mt5.order_send, **request)
        if result is None:
            return {"retcode": -1}
        return {"retcode": getattr(result, "retcode", -1)}

    async def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market book."""
        return await self._run(mt5.market_book_add, symbol)

    async def market_book_get(self, symbol: str) -> list[dict[str, Any]] | None:
        """Get market book."""
        book = await self._run(mt5.market_book_get, symbol)
        if book is None:
            return None
        return [
            {
                "type": getattr(entry, "type", 0),
                "price": getattr(entry, "price", 0.0),
                "volume": getattr(entry, "volume", 0),
                "volume_dbl": getattr(entry, "volume_dbl", 0.0),
            }
            for entry in book
        ]

    async def market_book_release(self, symbol: str) -> bool:
        """Release market book."""
        return await self._run(mt5.market_book_release, symbol)

    # ------------------------------------------------------------------
    # EA REST bridge delegation — chart operations via SYNX_EA on port
    # configured in bridge.ea_port (default 18765).  The EARestBridge
    # client is created lazily on first use and reused thereafter.
    # ------------------------------------------------------------------

    def _get_ea(self):
        """Return the lazily-created SYNXEABridge for chart/state operations."""
        if self._ea is None:
            from pathlib import Path

            from synx_mt5.bridge.ea_file_ipc import SYNXEABridge

            if self.config.ea_files_dir:
                files_dir = Path(self.config.ea_files_dir)
            elif self._terminal_data_path:
                files_dir = Path(self._terminal_data_path) / "MQL5" / "Files"
            else:
                # Last resort: ask MT5 directly (sync, only used before first chart call)
                info = mt5.terminal_info()
                data_path = getattr(info, "data_path", "") if info else ""
                files_dir = Path(data_path) / "MQL5" / "Files" if data_path else Path(".")

            self._ea = SYNXEABridge(files_dir)
        return self._ea

    async def ea_chart_list(self) -> list[dict[str, Any]]:
        """List all open charts via SYNX_EA REST bridge."""
        return await self._get_ea().ea_chart_list()

    async def ea_chart_open(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """Open a new chart window via SYNX_EA."""
        return await self._get_ea().ea_chart_open(symbol, timeframe)

    async def ea_chart_close(self, chart_id: int) -> dict[str, Any]:
        """Close a chart by ID via SYNX_EA."""
        return await self._get_ea().ea_chart_close(chart_id)

    async def ea_chart_screenshot(
        self, chart_id: int, width: int, height: int, align_to_right: bool
    ) -> dict[str, Any]:
        """Capture chart screenshot via SYNX_EA."""
        return await self._get_ea().ea_chart_screenshot(chart_id, width, height, align_to_right)

    async def ea_chart_set_symbol_timeframe(
        self, chart_id: int, symbol: str | None, timeframe: str | None
    ) -> None:
        """Change chart symbol/timeframe via SYNX_EA."""
        return await self._get_ea().ea_chart_set_symbol_timeframe(chart_id, symbol, timeframe)

    async def ea_chart_apply_template(self, chart_id: int, template_name: str) -> dict[str, Any]:
        """Apply a .tpl template to a chart via SYNX_EA."""
        return await self._get_ea().ea_chart_apply_template(chart_id, template_name)

    async def ea_chart_save_template(self, chart_id: int, template_name: str) -> dict[str, Any]:
        """Save chart as .tpl template via SYNX_EA."""
        return await self._get_ea().ea_chart_save_template(chart_id, template_name)

    async def ea_chart_navigate(self, chart_id: int, position: str, shift: int) -> dict[str, Any]:
        """Navigate chart scroll position via SYNX_EA."""
        return await self._get_ea().ea_chart_navigate(chart_id, position, shift)

    async def ea_chart_indicator_add(
        self,
        chart_id: int,
        indicator_path: str,
        window: int,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Add an indicator to a chart via SYNX_EA."""
        return await self._get_ea().ea_chart_indicator_add(chart_id, indicator_path, window, parameters)

    async def ea_chart_indicator_list(
        self, chart_id: int, window: int | None = None
    ) -> list[dict[str, Any]]:
        """List indicators on a chart via SYNX_EA."""
        return await self._get_ea().ea_chart_indicator_list(chart_id, window)

    async def ea_run_script(
        self, chart_id: int, script_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an MQL5 script on a chart via SYNX_EA."""
        return await self._get_ea().ea_run_script(chart_id, script_name, parameters)
