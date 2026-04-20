"""Composite Bridge - Dual-bridge mode for python_com + ea_file seamless experience.

Enables both bridges to work together with intelligent routing:
- Fast operations → python_com (direct API)
- EA-dependent operations → ea_file (SYNX_EA service)
- Automatic fallback when one fails
- Unified connection state management
"""

from typing import Any

import structlog

from synx_mt5.bridge.base import MT5Bridge
from synx_mt5.config import BridgeConfig

log = structlog.get_logger(__name__)


class CompositeBridge(MT5Bridge):
    """
    Composite bridge that manages both python_com and ea_file bridges.

    Routing strategy:
    - Fast read ops (symbol_info, copy_rates, ticks) → python_com
    - EA-only ops (chart_*, mql5_*, backtest_*) → ea_file
    - Order execution → python_com (with ea_file fallback)
    - Position/order queries → python_com (with ea_file fallback)

    Fallback chain when primary fails:
    - python_com fails → ea_file (if available)
    - Both fail → raise error
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self._primary = None  # python_com bridge
        self._secondary = None  # ea_file bridge
        self._metaeditor = None  # MetaEditor bridge for MQL5/backtest
        self._connected = False
        self._primary_connected = False
        self._secondary_connected = False

    async def _init_bridges(self) -> None:
        """Initialize both bridges lazily."""
        if self._primary is None:
            from synx_mt5.bridge.ea_file import EAFileBridge
            from synx_mt5.bridge.python_com import PythonCOMBridge

            self._primary = PythonCOMBridge(self.config)
            self._secondary = EAFileBridge(self.config)

    async def connect(self) -> bool:
        """Connect both bridges. Succeeds if at least one connects."""
        await self._init_bridges()

        log.info("composite_bridge_connecting")

        # Connect primary (python_com)
        try:
            self._primary_connected = await self._primary.connect()
            log.info("composite_bridge_primary_status", connected=self._primary_connected)
        except Exception as e:
            log.warning("composite_bridge_primary_failed", error=str(e))
            self._primary_connected = False

        # Connect secondary (ea_file)
        try:
            self._secondary_connected = await self._secondary.connect()
            log.info("composite_bridge_secondary_status", connected=self._secondary_connected)
        except Exception as e:
            log.warning("composite_bridge_secondary_failed", error=str(e))
            self._secondary_connected = False

        # Overall connected = at least one bridge connected
        self._connected = self._primary_connected or self._secondary_connected
        log.info("composite_bridge_connected", overall=self._connected, primary=self._primary_connected, secondary=self._secondary_connected)

        return self._connected

    async def disconnect(self) -> None:
        """Disconnect both bridges."""
        await self._init_bridges()

        if self._primary_connected:
            try:
                await self._primary.disconnect()
            except Exception as e:
                log.warning("composite_bridge_primary_disconnect_failed", error=str(e))

        if self._secondary_connected:
            try:
                await self._secondary.disconnect()
            except Exception as e:
                log.warning("composite_bridge_secondary_disconnect_failed", error=str(e))

        self._connected = False
        self._primary_connected = False
        self._secondary_connected = False

    async def is_connected(self) -> bool:
        """Check if at least one bridge is connected."""
        return self._connected

    async def _try_primary_or_fallback(
        self, op_name: str, primary_fn, fallback_fn
    ) -> Any:
        """Try primary bridge, fallback to secondary if it fails."""
        if self._primary_connected:
            try:
                result = await primary_fn()
                log.debug("composite_bridge_primary_success", op=op_name)
                return result
            except Exception as e:
                log.warning(
                    "composite_bridge_primary_failed_fallback",
                    op=op_name,
                    error=str(e),
                )
                if not self._secondary_connected:
                    raise

        # Fallback to secondary
        if self._secondary_connected:
            try:
                result = await fallback_fn()
                log.debug("composite_bridge_secondary_success", op=op_name)
                return result
            except Exception as e:
                log.error("composite_bridge_both_failed", op=op_name, error=str(e))
                raise

        raise RuntimeError(f"No bridges connected for operation: {op_name}")

    async def _use_primary(self, op_name: str, fn) -> Any:
        """Use only primary bridge (python_com)."""
        if not self._primary_connected:
            raise RuntimeError(f"Primary bridge not connected for operation: {op_name}")
        try:
            return await fn()
        except Exception as e:
            log.error("composite_bridge_primary_error", op=op_name, error=str(e))
            raise

    async def _use_secondary(self, op_name: str, fn) -> Any:
        """Use only secondary bridge (ea_file)."""
        if not self._secondary_connected:
            raise RuntimeError(f"Secondary bridge not connected for operation: {op_name}")
        try:
            return await fn()
        except Exception as e:
            log.error("composite_bridge_secondary_error", op=op_name, error=str(e))
            raise

    # =========================================================================
    # ROUTING: Fast operations use python_com
    # =========================================================================

    async def account_info(self) -> dict[str, Any]:
        """Get account info - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "account_info",
            lambda: self._primary.account_info(),
            lambda: self._secondary.account_info(),
        )

    async def terminal_info(self) -> dict[str, Any]:
        """Get terminal info - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "terminal_info",
            lambda: self._primary.terminal_info(),
            lambda: self._secondary.terminal_info(),
        )

    async def symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get symbol info - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "symbol_info",
            lambda: self._primary.symbol_info(symbol),
            lambda: self._secondary.symbol_info(symbol),
        )

    async def symbol_info_tick(self, symbol: str) -> dict[str, Any] | None:
        """Get current tick - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "symbol_info_tick",
            lambda: self._primary.symbol_info_tick(symbol),
            lambda: self._secondary.symbol_info_tick(symbol),
        )

    async def symbols_total(self) -> int:
        """Get total symbols - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "symbols_total",
            lambda: self._primary.symbols_total(),
            lambda: self._secondary.symbols_total(),
        )

    async def symbols_get(self, group: str = "*") -> list[dict[str, Any]]:
        """Get symbols - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "symbols_get",
            lambda: self._primary.symbols_get(group),
            lambda: self._secondary.symbols_get(group),
        )

    async def symbol_select(self, symbol: str, select: bool = True) -> bool:
        """Select symbol - use primary."""
        return await self._try_primary_or_fallback(
            "symbol_select",
            lambda: self._primary.symbol_select(symbol, select),
            lambda: self._secondary.symbol_select(symbol, select),
        )

    async def copy_rates_from_pos(
        self, symbol: str, timeframe: str, start_pos: int, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "copy_rates_from_pos",
            lambda: self._primary.copy_rates_from_pos(symbol, timeframe, start_pos, count),
            lambda: self._secondary.copy_rates_from_pos(symbol, timeframe, start_pos, count),
        )

    async def copy_rates_from(
        self, symbol: str, timeframe: str, date_from: str, count: int
    ) -> list[dict[str, Any]]:
        """Copy rates from date - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "copy_rates_from",
            lambda: self._primary.copy_rates_from(symbol, timeframe, date_from, count),
            lambda: self._secondary.copy_rates_from(symbol, timeframe, date_from, count),
        )

    async def copy_rates_range(
        self, symbol: str, timeframe: str, date_from: str, date_to: str
    ) -> list[dict[str, Any]]:
        """Copy rates range - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "copy_rates_range",
            lambda: self._primary.copy_rates_range(symbol, timeframe, date_from, date_to),
            lambda: self._secondary.copy_rates_range(symbol, timeframe, date_from, date_to),
        )

    async def copy_ticks_from(
        self, symbol: str, date_from: str, count: int, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "copy_ticks_from",
            lambda: self._primary.copy_ticks_from(symbol, date_from, count, flags),
            lambda: self._secondary.copy_ticks_from(symbol, date_from, count, flags),
        )

    async def copy_ticks_range(
        self, symbol: str, date_from: str, date_to: str, flags: str = "COPY_TICKS_ALL"
    ) -> list[dict[str, Any]]:
        """Copy ticks range - use primary (fast)."""
        return await self._try_primary_or_fallback(
            "copy_ticks_range",
            lambda: self._primary.copy_ticks_range(symbol, date_from, date_to, flags),
            lambda: self._secondary.copy_ticks_range(symbol, date_from, date_to, flags),
        )

    async def positions_total(self) -> int:
        """Get total positions - use primary."""
        return await self._try_primary_or_fallback(
            "positions_total",
            lambda: self._primary.positions_total(),
            lambda: self._secondary.positions_total(),
        )

    async def positions_get(
        self, symbol: str = "", ticket: int = 0
    ) -> list[dict[str, Any]]:
        """Get positions - use primary."""
        return await self._try_primary_or_fallback(
            "positions_get",
            lambda: self._primary.positions_get(symbol, ticket),
            lambda: self._secondary.positions_get(symbol, ticket),
        )

    async def orders_total(self) -> int:
        """Get total orders - use primary."""
        return await self._try_primary_or_fallback(
            "orders_total",
            lambda: self._primary.orders_total(),
            lambda: self._secondary.orders_total(),
        )

    async def orders_get(self, symbol: str = "", ticket: int = 0) -> list[dict[str, Any]]:
        """Get orders - use primary."""
        return await self._try_primary_or_fallback(
            "orders_get",
            lambda: self._primary.orders_get(symbol, ticket),
            lambda: self._secondary.orders_get(symbol, ticket),
        )

    async def order_calc_margin(
        self, order_type: str, symbol: str, volume: float, price: float
    ) -> dict[str, Any] | None:
        """Calculate margin - use primary."""
        return await self._try_primary_or_fallback(
            "order_calc_margin",
            lambda: self._primary.order_calc_margin(order_type, symbol, volume, price),
            lambda: self._secondary.order_calc_margin(order_type, symbol, volume, price),
        )

    async def order_calc_profit(
        self,
        order_type: str,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> dict[str, Any] | None:
        """Calculate profit - use primary."""
        return await self._try_primary_or_fallback(
            "order_calc_profit",
            lambda: self._primary.order_calc_profit(
                order_type, symbol, volume, price_open, price_close
            ),
            lambda: self._secondary.order_calc_profit(
                order_type, symbol, volume, price_open, price_close
            ),
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
        """Check order - use primary."""
        return await self._try_primary_or_fallback(
            "order_check",
            lambda: self._primary.order_check(symbol, order_type, volume, price, sl, tp),
            lambda: self._secondary.order_check(symbol, order_type, volume, price, sl, tp),
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
        """Send order - use primary with fallback."""
        return await self._try_primary_or_fallback(
            "order_send",
            lambda: self._primary.order_send(
                symbol, order_type, volume, price, sl, tp, magic, comment
            ),
            lambda: self._secondary.order_send(
                symbol, order_type, volume, price, sl, tp, magic, comment
            ),
        )

    async def position_close(
        self, ticket: int, volume: float = 0, deviation: int = 20
    ) -> dict[str, Any]:
        """Close position - use primary."""
        return await self._try_primary_or_fallback(
            "position_close",
            lambda: self._primary.position_close(ticket, volume, deviation),
            lambda: self._secondary.position_close(ticket, volume, deviation),
        )

    async def position_modify(self, ticket: int, sl: float, tp: float) -> dict[str, Any]:
        """Modify position - use primary."""
        return await self._try_primary_or_fallback(
            "position_modify",
            lambda: self._primary.position_modify(ticket, sl, tp),
            lambda: self._secondary.position_modify(ticket, sl, tp),
        )

    async def order_modify(
        self, ticket: int, price: float, sl: float, tp: float
    ) -> dict[str, Any]:
        """Modify order - use primary."""
        return await self._try_primary_or_fallback(
            "order_modify",
            lambda: self._primary.order_modify(ticket, price, sl, tp),
            lambda: self._secondary.order_modify(ticket, price, sl, tp),
        )

    async def order_cancel(self, ticket: int) -> dict[str, Any]:
        """Cancel order - use primary."""
        return await self._try_primary_or_fallback(
            "order_cancel",
            lambda: self._primary.order_cancel(ticket),
            lambda: self._secondary.order_cancel(ticket),
        )

    async def history_orders_total(self, date_from: str, date_to: str) -> int:
        """Get history orders total - use primary."""
        return await self._try_primary_or_fallback(
            "history_orders_total",
            lambda: self._primary.history_orders_total(date_from, date_to),
            lambda: self._secondary.history_orders_total(date_from, date_to),
        )

    async def history_orders_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get history orders - use primary."""
        return await self._try_primary_or_fallback(
            "history_orders_get",
            lambda: self._primary.history_orders_get(date_from, date_to, symbol),
            lambda: self._secondary.history_orders_get(date_from, date_to, symbol),
        )

    async def history_deals_total(self, date_from: str, date_to: str) -> int:
        """Get history deals total - use primary."""
        return await self._try_primary_or_fallback(
            "history_deals_total",
            lambda: self._primary.history_deals_total(date_from, date_to),
            lambda: self._secondary.history_deals_total(date_from, date_to),
        )

    async def history_deals_get(
        self, date_from: str, date_to: str, symbol: str = ""
    ) -> list[dict[str, Any]]:
        """Get history deals - use primary."""
        return await self._try_primary_or_fallback(
            "history_deals_get",
            lambda: self._primary.history_deals_get(date_from, date_to, symbol),
            lambda: self._secondary.history_deals_get(date_from, date_to, symbol),
        )

    async def market_book_add(self, symbol: str) -> bool:
        """Subscribe to market book - use primary."""
        return await self._try_primary_or_fallback(
            "market_book_add",
            lambda: self._primary.market_book_add(symbol),
            lambda: self._secondary.market_book_add(symbol),
        )

    async def market_book_get(self, symbol: str) -> list[dict[str, Any]] | None:
        """Get market book - use primary."""
        return await self._try_primary_or_fallback(
            "market_book_get",
            lambda: self._primary.market_book_get(symbol),
            lambda: self._secondary.market_book_get(symbol),
        )

    async def market_book_release(self, symbol: str) -> bool:
        """Release market book - use primary."""
        return await self._try_primary_or_fallback(
            "market_book_release",
            lambda: self._primary.market_book_release(symbol),
            lambda: self._secondary.market_book_release(symbol),
        )

    # =========================================================================
    # CHART OPERATIONS (EA-dependent - use secondary bridge)
    # =========================================================================

    async def ea_chart_list(self) -> list[dict[str, Any]]:
        """List all open charts - use secondary (ea_file)."""
        if not self._secondary_connected:
            log.warning("composite_bridge_chart_unavailable", reason="secondary_not_connected")
            return []
        try:
            return await self._secondary.ea_chart_list()
        except Exception as e:
            log.error("composite_bridge_chart_list_error", error=str(e))
            return []

    async def ea_chart_open(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """Open a new chart - use secondary (ea_file)."""
        if not self._secondary_connected:
            msg = "Chart operations require secondary bridge (ea_file) to be connected"
            raise RuntimeError(msg)
        return await self._use_secondary(
            "ea_chart_open",
            lambda: self._secondary.ea_chart_open(symbol, timeframe),
        )

    async def ea_chart_close(self, chart_id: int) -> dict[str, Any]:
        """Close a chart - use secondary (ea_file)."""
        if not self._secondary_connected:
            msg = "Chart operations require secondary bridge (ea_file) to be connected"
            raise RuntimeError(msg)
        return await self._use_secondary(
            "ea_chart_close", lambda: self._secondary.ea_chart_close(chart_id)
        )

    async def ea_chart_indicator_add(
        self,
        chart_id: int,
        indicator_path: str,
        window: int = 0,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add indicator to chart - use secondary (ea_file)."""
        if not self._secondary_connected:
            msg = "Chart operations require secondary bridge (ea_file) to be connected"
            raise RuntimeError(msg)
        return await self._use_secondary(
            "ea_chart_indicator_add",
            lambda: self._secondary.ea_chart_indicator_add(
                chart_id, indicator_path, window, parameters or {}
            ),
        )

    async def ea_chart_indicator_list(
        self, chart_id: int, window: int | None = None
    ) -> list[dict[str, Any]]:
        """List indicators on chart - use secondary (ea_file)."""
        if not self._secondary_connected:
            log.warning(
                "composite_bridge_chart_unavailable", reason="secondary_not_connected"
            )
            return []
        try:
            return await self._secondary.ea_chart_indicator_list(chart_id, window)
        except Exception as e:
            log.error("composite_bridge_chart_indicator_list_error", error=str(e))
            return []

    async def ea_chart_indicator_delete(
        self, chart_id: int, window: int, index: int
    ) -> dict[str, Any]:
        """Delete indicator from chart - use secondary (ea_file)."""
        if not self._secondary_connected:
            msg = "Chart operations require secondary bridge (ea_file) to be connected"
            raise RuntimeError(msg)
        return await self._use_secondary(
            "ea_chart_indicator_delete",
            lambda: self._secondary.ea_chart_indicator_delete(chart_id, window, index),
        )

    async def ea_chart_screenshot(
        self,
        chart_id: int,
        width: int = 1280,
        height: int = 720,
        align_to_right: bool = True,
    ) -> dict[str, Any]:
        """Capture chart as PNG - use secondary (ea_file)."""
        if not self._secondary_connected:
            msg = "Chart operations require secondary bridge (ea_file) to be connected"
            raise RuntimeError(msg)
        return await self._use_secondary(
            "ea_chart_screenshot",
            lambda: self._secondary.ea_chart_screenshot(
                chart_id, width, height, align_to_right
            ),
        )

    async def ea_chart_apply_template(
        self, chart_id: int, template_name: str
    ) -> dict[str, Any]:
        """Apply template to chart - use secondary (ea_file)."""
        if not self._secondary_connected:
            msg = "Chart operations require secondary bridge (ea_file) to be connected"
            raise RuntimeError(msg)
        return await self._use_secondary(
            "ea_chart_apply_template",
            lambda: self._secondary.ea_chart_apply_template(chart_id, template_name),
        )

    async def ea_chart_save_template(
        self, chart_id: int, template_name: str
    ) -> dict[str, Any]:
        """Save chart as template - use secondary (ea_file)."""
        if not self._secondary_connected:
            msg = "Chart operations require secondary bridge (ea_file) to be connected"
            raise RuntimeError(msg)
        return await self._use_secondary(
            "ea_chart_save_template",
            lambda: self._secondary.ea_chart_save_template(chart_id, template_name),
        )

    async def ea_chart_navigate(
        self, chart_id: int, position: str = "current", shift: int = 0
    ) -> dict[str, Any]:
        """Navigate chart - use secondary (ea_file)."""
        if not self._secondary_connected:
            msg = "Chart operations require secondary bridge (ea_file) to be connected"
            raise RuntimeError(msg)
        return await self._use_secondary(
            "ea_chart_navigate",
            lambda: self._secondary.ea_chart_navigate(chart_id, position, shift),
        )

    async def ea_chart_set_symbol_timeframe(
        self, chart_id: int, symbol: str | None = None, timeframe: str | None = None
    ) -> dict[str, Any]:
        """Change chart symbol/timeframe - use secondary (ea_file) if available."""
        if not self._secondary_connected:
            msg = "Chart operations require secondary bridge (ea_file) to be connected"
            raise RuntimeError(msg)
        if hasattr(self._secondary, "ea_chart_set_symbol_timeframe"):
            return await self._use_secondary(
                "ea_chart_set_symbol_timeframe",
                lambda: self._secondary.ea_chart_set_symbol_timeframe(
                    chart_id, symbol, timeframe
                ),
            )
        msg = "ea_chart_set_symbol_timeframe not implemented in ea_file bridge"
        raise NotImplementedError(msg)

    async def ea_chart_attach_ea(self, chart_id: int, ea_name: str) -> dict[str, Any]:
        """Attach an Expert Advisor to a chart - use secondary (ea_file)."""
        if not self._secondary_connected:
            raise RuntimeError("Chart operations require secondary bridge (ea_file) to be connected")
        return await self._use_secondary(
            "ea_chart_attach_ea",
            lambda: self._secondary.ea_chart_attach_ea(chart_id, ea_name)
        )

    async def ea_chart_remove_ea(self, chart_id: int) -> dict[str, Any]:
        """Remove Expert Advisor from a chart - use secondary (ea_file)."""
        if not self._secondary_connected:
            raise RuntimeError("Chart operations require secondary bridge (ea_file) to be connected")
        return await self._use_secondary(
            "ea_chart_remove_ea",
            lambda: self._secondary.ea_chart_remove_ea(chart_id)
        )

    # =========================================================================
    # BACKTEST OPERATIONS (MetaEditor dependent)
    # =========================================================================

    async def metaeditor_backtest(
        self,
        ea_name: str,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
        initial_deposit: float = 10000.0,
        leverage: int = 100,
        model: str = "every_tick",
    ) -> dict[str, Any]:
        """Trigger backtest - use MetaEditor bridge."""
        if self._metaeditor is None:
            from synx_mt5.bridge.metaeditor import MetaEditorBridge
            from synx_mt5.config import MQL5Config

            mql5_config = MQL5Config(
                metaeditor_path=None,  # Auto-detect
                mql5_dir=None,  # Auto-detect
                max_file_size_kb=512,
                compile_timeout_seconds=60,
            )
            self._metaeditor = MetaEditorBridge(
                config=mql5_config,
                terminal_data_path=None,
            )

        try:
            result = await self._metaeditor.metaeditor_backtest(
                ea_name=ea_name,
                symbol=symbol,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
                initial_deposit=initial_deposit,
                leverage=leverage,
                model=model,
            )
            log.info("composite_bridge_backtest_success", ea_name=ea_name)
            return result
        except Exception as e:
            log.error("composite_bridge_backtest_error", error=str(e))
            return {"started": False, "error": str(e)}

    def get_compile_errors(self, filename: str | None = None) -> dict[str, Any]:
        """Retrieve MetaEditor compilation errors - use MetaEditor bridge."""
        if self._metaeditor is None:
            from synx_mt5.bridge.metaeditor import MetaEditorBridge
            from synx_mt5.config import MQL5Config

            mql5_config = MQL5Config(
                metaeditor_path=None,
                mql5_dir=None,
                max_file_size_kb=512,
                compile_timeout_seconds=60,
            )
            self._metaeditor = MetaEditorBridge(
                config=mql5_config,
                terminal_data_path=None,
            )

        try:
            result = self._metaeditor.get_compile_errors(filename)
            log.info("composite_bridge_get_compile_errors_success", filename=filename)
            return result
        except Exception as e:
            log.error("composite_bridge_get_compile_errors_error", error=str(e))
            return {
                "error_count": 0,
                "warning_count": 0,
                "errors": [{"type": "error", "message": str(e)}],
                "source_file": filename,
            }
