"""EA File Bridge - File-based IPC bridge for SYNX_EA service."""

import asyncio
import contextlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from synx_mt5.bridge.base import MT5Bridge
from synx_mt5.config import BridgeConfig


class EAFileBridge(MT5Bridge):
    """Bridge using SYNX_EA file-based IPC.

    EA polls FILE_COMMON root for files matching: synx__cmd*.json
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self._common_files = Path(os.path.expandvars(r"%APPDATA%\MetaQuotes\Terminal\Common\Files"))
        self._connected = False
        self._timeout = config.ea_timeout_seconds

    def _state_file(self, name: str) -> Path:
        """Get state file path - files in root: synx__state<name>.json"""
        # Handle special cases for file names
        if name == "_account":
            return self._common_files / "synx__stateaccount.json"
        elif name == "_terminal":
            return self._common_files / "synx__stateterminal.json"
        elif name == "_charts":
            return self._common_files / "synx__statecharts.json"
        elif name == "_positions":
            return self._common_files / "synx__statepositions.json"
        elif name == "_symbols":
            return self._common_files / "synx__statesymbols.json"
        elif name == "_health":
            return self._common_files / "synx__statehealth.json"
        else:
            return self._common_files / f"synx__state{name}.json"

    async def connect(self) -> bool:
        """Connect - verify file system is accessible."""
        import json

        import structlog

        logger = structlog.get_logger(__name__)
        try:
            exists = self._common_files.exists()
            logger.info(
                "ea_file_bridge_connect",
                path=str(self._common_files),
                exists=exists,
                mode="ea_file",
            )
            self._connected = exists

            # Test reading a state file
            test_file = self._common_files / "synx__stateaccount.json"
            if test_file.exists():
                with open(test_file) as f:
                    data = json.load(f)
                balance = data.get("balance", 0)
                equity = data.get("equity", 0)
                logger.info("ea_file_bridge_state_test", balance=balance, equity=equity)
                return True
            else:
                logger.warning("ea_file_bridge_no_state_file", path=str(test_file))
                return False
        except Exception as e:
            logger.error("ea_file_bridge_connect_error", path=str(self._common_files), error=str(e))
            self._connected = False
            return False

    def _verify_filesystem(self) -> bool:
        """Verify Common Files is accessible."""
        return self._common_files.exists()

    def _resolve_chart_id(self, approx_id: int) -> int:
        """Resolve a possibly-precision-lost chart ID to the real MT5 chart ID.

        Chart IDs are 64-bit integers that exceed JS Number.MAX_SAFE_INTEGER,
        so MCP clients lose the last ~3 digits. We match by closest within 100.
        """
        state_file = self._state_file("_charts")
        if not state_file.exists():
            return approx_id
        with contextlib.suppress(Exception):
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
            charts = data.get("charts", [])
            for c in charts:
                cid = int(c.get("id", 0))
                if cid == approx_id:
                    return approx_id
            if charts:
                best = min(charts, key=lambda c: abs(int(c.get("id", 0)) - approx_id))
                best_id = int(best.get("id", 0))
                if abs(best_id - approx_id) < 100:
                    return best_id
        return approx_id

    async def _execute_cmd(self, cmd: str, **kwargs) -> dict[str, Any]:
        """Execute file-based command - writes to FILE_COMMON ROOT."""
        import structlog
        logger = structlog.get_logger(__name__)

        if not self._connected:
            return {"error": "Not connected", "code": 503}

        req_id = str(uuid.uuid4())[:8]

        cmd_json = {
            "cmd": cmd,
            "req_id": req_id,
            **kwargs
        }

        logger.info("execute_cmd", cmd=cmd, req_id=req_id, kwargs=kwargs)

        # Write to ROOT of Common\Files with pattern: cmd_<req_id>.json
        cmd_file = self._common_files / f"cmd_{req_id}.json"

        try:
            with open(cmd_file, "w", encoding="utf-8") as f:
                json.dump(cmd_json, f)
        except Exception as e:
            return {"error": f"Failed to write command: {e}", "code": 500}

        # Response file pattern: resp_<req_id>.json
        resp_file = self._common_files / f"resp_{req_id}.json"
        start_time = time.time()

        while time.time() - start_time < self._timeout:
            if resp_file.exists():
                try:
                    with open(resp_file, encoding="utf-8") as f:
                        response = json.load(f)
                    resp_file.unlink()
                    logger.info("execute_cmd_response", cmd=cmd, response=response)
                    return response.get("data", response)
                except Exception as e:
                    logger.error("execute_cmd_read_error", cmd=cmd, error=str(e))
                    return {"error": f"Failed to read response: {e}", "code": 500}
            await asyncio.sleep(0.1)

        # Cleanup cmd file if no response
        cmd_file.unlink(missing_ok=True)
        logger.warning("execute_cmd_timeout", cmd=cmd, req_id=req_id)
        return {"error": "Command timeout", "code": 408}

    async def account_info(self) -> dict[str, Any]:
        """Get account info."""
        state_file = self._state_file("_account")
        if not state_file.exists():
            return {"error": "No data", "code": 404}
        with open(state_file, encoding="utf-8") as f:
            return json.load(f)

    async def terminal_info(self) -> dict[str, Any]:
        """Get terminal info."""
        state_file = self._state_file("_terminal")
        if not state_file.exists():
            return {"error": "No data", "code": 404}
        with open(state_file, encoding="utf-8") as f:
            return json.load(f)

    async def symbols_total(self) -> int:
        data = await self.symbols_get()
        return len(data) if isinstance(data, list) else len(data.get("symbols", []))

    async def symbols_get(self, group: str = "*") -> list[dict[str, Any]]:
        state_file = self._state_file("_symbols")
        if not state_file.exists():
            return []
        with open(state_file, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("symbols", [])

    async def copy_rates_from_pos(
        self, symbol: str, timeframe: str, start_pos: int, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates from position."""
        result = await self._execute_cmd(
            "get_rates",
            symbol=symbol,
            timeframe=timeframe,
            start=start_pos,
            count=count
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("rates", [])
        return []

    async def positions_total(self) -> int:
        """Get positions total."""
        data = await self.positions_get()
        return len(data.get("positions", []))

    async def positions_get(self, symbol: str = "", ticket: int = 0) -> list[dict[str, Any]]:
        """Get positions."""
        state_file = self._state_file("_positions")
        if not state_file.exists():
            return []
        with open(state_file, encoding="utf-8") as f:
            data = json.load(f)
        positions = data.get("positions", [])
        if ticket:
            return [p for p in positions if p.get("ticket") == ticket]
        if symbol:
            return [p for p in positions if p.get("symbol") == symbol]
        return positions

    async def orders_get(self, symbol: str = "", ticket: int = 0) -> list[dict[str, Any]]:
        """Get pending orders."""
        return []

    async def orders_total(self) -> int:
        return 0

    async def order_send(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float = 0,
        sl: float = 0,
        tp: float = 0,
        magic: int = 0,
        comment: str = "",
    ) -> dict[str, Any]:
        """Send order."""
        type_map = {
            "ORDER_TYPE_BUY": 0,
            "ORDER_TYPE_SELL": 1,
            "ORDER_TYPE_BUY_LIMIT": 2,
            "ORDER_TYPE_SELL_LIMIT": 3,
            "ORDER_TYPE_BUY_STOP": 4,
            "ORDER_TYPE_SELL_STOP": 5,
        }
        order_type_int = type_map.get(order_type, 0)
        return await self._execute_cmd(
            "order_send",
            symbol=symbol,
            type=order_type_int,
            volume=volume,
            price=price,
            sl=sl if sl else 0,
            tp=tp if tp else 0,
            magic=magic,
            comment=comment
        )

    async def position_close(
        self, ticket: int, volume: float = 0, deviation: int = 20
    ) -> dict[str, Any]:
        """Close position."""
        return await self._execute_cmd(
            "position_close",
            ticket=ticket
        )

    async def position_modify(self, ticket: int, sl: float, tp: float) -> dict[str, Any]:
        """Modify position."""
        return {"error": "Not implemented via file IPC", "code": 501}

    async def order_modify(self, ticket: int, price: float, sl: float, tp: float) -> dict[str, Any]:
        """Modify order."""
        return {"error": "Not implemented via file IPC", "code": 501}

    async def order_cancel(self, ticket: int) -> dict[str, Any]:
        """Cancel order."""
        return {"error": "Not implemented via file IPC", "code": 501}

    async def ea_chart_list(self) -> list[dict[str, Any]]:
        """List all open charts."""
        import structlog
        logger = structlog.get_logger(__name__)

        state_file = self._state_file("_charts")

        if not state_file.exists():
            return []
        with open(state_file, encoding="utf-8") as f:
            data = json.load(f)

        charts = data.get("charts", [])

        # Map state file IDs to actual MT5 ChartFirst IDs
        # The state file uses IDs that ChartFirst returns
        # Just return as-is - the state file IDs should match
        logger.info("ea_chart_list_result", charts=charts)
        return charts

    async def ea_chart_open(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """Open a new chart."""
        return {"error": "Not implemented via file IPC", "code": 501}

    async def ea_chart_close(self, chart_id: int) -> dict[str, Any]:
        """Close a chart."""
        return {"error": "Not implemented via file IPC", "code": 501}

    async def ea_chart_indicator_add(
        self,
        chart_id: int,
        indicator_path: str,
        window: int,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Add an indicator to a chart."""
        chart_id = self._resolve_chart_id(chart_id)
        return await self._execute_cmd(
            "chart_indicator_add",
            chart_id=str(chart_id),  # Send as string to preserve 64-bit precision
            indicator=indicator_path,
            window=window,
            **parameters
        )

    async def ea_chart_indicator_list(
        self, chart_id: int, window: int | None = None
    ) -> list[dict[str, Any]]:
        """List indicators on a chart."""
        import structlog
        logger = structlog.get_logger(__name__)
        chart_id = self._resolve_chart_id(chart_id)
        result = await self._execute_cmd(
            "chart_indicator_list",
            chart_id=str(chart_id),  # Send as string to preserve 64-bit precision
            window=window or 0
        )
        logger.info("ea_chart_indicator_list_result", result=result, chart_id=chart_id)
        return result

    async def ea_chart_indicator_delete(
        self, chart_id: int, window: int, index: int
    ) -> dict[str, Any]:
        """Delete indicator from chart."""
        chart_id = self._resolve_chart_id(chart_id)
        return await self._execute_cmd(
            "chart_indicator_delete",
            chart_id=chart_id,
            window=window,
            index=index
        )

    async def ea_chart_screenshot(
        self, chart_id: int, width: int, height: int, align_to_right: bool
    ) -> dict[str, Any]:
        """Capture chart as PNG and return base64-encoded image."""
        import asyncio
        import base64
        import time as _time

        chart_id = self._resolve_chart_id(chart_id)
        result = await self._execute_cmd(
            "screenshot",
            chart_id=chart_id,
            width=width,
            height=height,
            align_right=align_to_right
        )
        if "error" in result:
            return result
        filename = result.get("filename", "")
        if not filename:
            return {"error": "No filename returned", "code": 500}
        png_path = self._common_files / filename
        deadline = _time.monotonic() + 5.0
        while _time.monotonic() < deadline:
            if png_path.exists():
                break
            await asyncio.sleep(0.1)
        if not png_path.exists():
            return {"error": f"Screenshot file not found: {filename}", "code": 404}
        try:
            image_b64 = base64.b64encode(png_path.read_bytes()).decode("utf-8")
            png_path.unlink(missing_ok=True)
            return {"image_base64": image_b64, "filename": filename, "status": "ok"}
        except Exception as e:
            return {"error": f"Failed to read screenshot: {e}", "code": 500}

    async def ea_chart_navigate(
        self, chart_id: int, position: str = "current", shift: int = 0
    ) -> dict[str, Any]:
        """Navigate chart - delegate to ea_file command."""
        chart_id = self._resolve_chart_id(chart_id)
        return await self._execute_cmd(
            "chart_navigate",
            chart_id=str(chart_id),
            position=position,
            shift=shift
        )

    async def ea_chart_apply_template(self, chart_id: int, template_name: str) -> dict[str, Any]:
        """Apply template to chart - delegate to ea_file command."""
        chart_id = self._resolve_chart_id(chart_id)
        return await self._execute_cmd(
            "chart_apply_template",
            chart_id=str(chart_id),
            template=template_name
        )

    async def ea_chart_save_template(self, chart_id: int, template_name: str) -> dict[str, Any]:
        """Save chart as template - delegate to ea_file command."""
        chart_id = self._resolve_chart_id(chart_id)
        return await self._execute_cmd(
            "chart_save_template",
            chart_id=str(chart_id),
            template=template_name
        )

    async def ea_chart_set_symbol_timeframe(
        self, chart_id: int, symbol: str | None = None, timeframe: str | None = None
    ) -> dict[str, Any]:
        """Change chart symbol/timeframe - delegate to ea_file command."""
        chart_id = self._resolve_chart_id(chart_id)
        return await self._execute_cmd(
            "chart_set_symbol_timeframe",
            chart_id=str(chart_id),
            symbol=symbol or "",
            timeframe=timeframe or ""
        )

    async def ea_chart_attach_ea(self, chart_id: int, ea_name: str) -> dict[str, Any]:
        """Attach an Expert Advisor to a chart."""
        chart_id = self._resolve_chart_id(chart_id)
        return await self._execute_cmd(
            "chart_attach_ea",
            chart_id=str(chart_id),
            ea_name=ea_name
        )

    async def ea_chart_remove_ea(self, chart_id: int) -> dict[str, Any]:
        """Remove/detach Expert Advisor from a chart."""
        chart_id = self._resolve_chart_id(chart_id)
        return await self._execute_cmd(
            "chart_remove_ea",
            chart_id=str(chart_id)
        )

    async def order_calc_margin(
        self, order_type: str, symbol: str, volume: float, price: float
    ) -> dict[str, Any] | None:
        """Calculate margin."""
        return await self._execute_cmd(
            "order_calc_margin",
            order_type=order_type,
            symbol=symbol,
            volume=volume,
            price=price,
        )

    async def order_calc_profit(
        self, order_type: str, symbol: str, volume: float, price_open: float, price_close: float
    ) -> dict[str, Any] | None:
        """Calculate profit."""
        return await self._execute_cmd(
            "order_calc_profit",
            order_type=order_type,
            symbol=symbol,
            volume=volume,
            price_open=price_open,
            price_close=price_close,
        )

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
        return await self._execute_cmd(
            "order_check",
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
        )

    async def disconnect(self) -> None:
        """Disconnect from bridge."""
        self._connected = False

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected and self._verify_filesystem()

    async def symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get symbol info."""
        state_file = self._state_file("_symbols")
        if not state_file.exists():
            return None
        with open(state_file, encoding="utf-8") as f:
            data = json.load(f)
        symbols = data.get("symbols", [])
        symbol_upper = symbol.upper()
        for s in symbols:
            name = (s.get("name") or s.get("symbol") or "").upper()
            if name == symbol_upper:
                return s
        return None

    async def symbol_info_tick(self, symbol: str) -> dict[str, Any] | None:
        """Get current tick for symbol."""
        return await self._execute_cmd("symbol_info_tick", symbol=symbol)

    async def symbol_select(self, symbol: str, select: bool = True) -> bool:
        """Add or remove symbol from MarketWatch."""
        return await self._execute_cmd("symbol_select", symbol=symbol, select=select)

    async def copy_rates_from(
        self, symbol: str, timeframe: str, date_from: str, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates from datetime."""
        result = await self._execute_cmd(
            "get_rates",
            symbol=symbol,
            timeframe=timeframe,
            date_from=date_from,
            count=count
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("rates", [])
        return []

    async def copy_rates_range(
        self, symbol: str, timeframe: str, date_from: str, date_to: str
    ) -> list[dict[str, Any]]:
        """Copy rates in datetime range."""
        result = await self._execute_cmd(
            "get_rates_range",
            symbol=symbol,
            timeframe=timeframe,
            date_from=date_from,
            date_to=date_to
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("rates", [])
        return []

    async def copy_ticks_from(
        self, symbol: str, date_from: str, count: int, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks from datetime."""
        result = await self._execute_cmd(
            "get_ticks",
            symbol=symbol,
            date_from=date_from,
            count=count,
            flags=flags
        )
        if isinstance(result, dict):
            return result.get("ticks", [])
        return result if isinstance(result, list) else []

    async def copy_ticks_range(
        self, symbol: str, date_from: str, date_to: str, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks in datetime range."""
        result = await self._execute_cmd(
            "get_ticks_range",
            symbol=symbol,
            date_from=date_from,
            date_to=date_to,
            flags=flags
        )
        if isinstance(result, dict):
            return result.get("ticks", [])
        return result if isinstance(result, list) else []

    async def history_orders_total(self, date_from: str, date_to: str) -> int:
        """Get count of historical orders."""
        return 0

    async def history_orders_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get historical orders."""
        return []

    async def history_deals_total(self, date_from: str, date_to: str) -> int:
        """Get count of historical deals."""
        return 0

    async def history_deals_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get historical deals."""
        return []

    async def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market book (DOM)."""
        return await self._execute_cmd("market_book_add", symbol=symbol)

    async def market_book_get(self, symbol: str) -> list[dict[str, Any]] | None:
        """Get market book entries."""
        return await self._execute_cmd("market_book_get", symbol=symbol)

    async def market_book_release(self, symbol: str) -> bool:
        """Release market book subscription."""
        return await self._execute_cmd("market_book_release", symbol=symbol)
