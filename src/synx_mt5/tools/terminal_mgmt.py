"""Terminal Management Tools - Terminal info, symbol selection, and pre-trade calculations."""

from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType
from synx_mt5.security.injection_shield import sanitise_string

log = structlog.get_logger(__name__)


class TerminalInfoOutput(BaseModel):
    """Output for get_terminal_info tool."""

    version: str | None = None
    build: int | None = None
    path: str | None = None
    data_path: str | None = None
    community_account: str | bool | None = None
    community_balance: float | None = None
    connected: bool | None = None
    trade_allowed: bool | None = None
    trade_expert: bool | None = None
    dlls_allowed: bool | None = None
    mqid: bool | None = None
    ping_last: int | None = None
    language: str | None = None
    company: str | None = None
    name: str | None = None


class SymbolSelectInput(BaseModel):
    """Input for symbol_select tool."""

    symbol: str = Field(min_length=1, max_length=32)
    enable: bool = Field(default=True)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "symbol_select:symbol").upper()


class OrderCalcMarginInput(BaseModel):
    """Input for order_calc_margin tool."""

    order_type: str
    symbol: str = Field(min_length=1, max_length=32)
    volume: float = Field(gt=0)
    price: float = Field(gt=0)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "order_calc_margin:symbol").upper()


class OrderCalcProfitInput(BaseModel):
    """Input for order_calc_profit tool."""

    order_type: str
    symbol: str = Field(min_length=1, max_length=32)
    volume: float = Field(gt=0)
    price_open: float = Field(gt=0)
    price_close: float = Field(gt=0)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "order_calc_profit:symbol").upper()


class OrderCheckInput(BaseModel):
    """Input for order_check tool."""

    symbol: str = Field(min_length=1, max_length=32)
    volume: float = Field(gt=0)
    order_type: str
    price: float = Field(ge=0)
    sl: float | None = Field(default=None, ge=0)
    tp: float | None = Field(default=None, ge=0)
    comment: str | None = None


class TerminalMgmtService:
    """
    Service layer for terminal management operations.
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
    ):
        self.bridge = bridge
        self.audit = audit

    async def get_terminal_info(self) -> TerminalInfoOutput:
        """Get full terminal status and environment information."""
        info = await self.bridge.terminal_info()

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_terminal_info",
            },
        )

        return TerminalInfoOutput(
            version=info.get("version", ""),
            build=info.get("build", 0),
            path=info.get("path", ""),
            data_path=info.get("data_path", ""),
            community_account=info.get("community_account", ""),
            community_balance=info.get("community_balance", 0.0),
            connected=info.get("connected", False),
            trade_allowed=info.get("trade_allowed", False),
            trade_expert=info.get("trade_expert", False),
            dlls_allowed=info.get("dlls_allowed", False),
            mqid=info.get("mqid", False),
            ping_last=info.get("ping_last", 0),
            language=info.get("language", ""),
            company=info.get("company", ""),
            name=info.get("name", ""),
        )

    async def symbol_select(
        self,
        symbol: str,
        enable: bool = True,
    ) -> dict[str, Any]:
        """Add or remove symbol from MarketWatch."""
        result = await self.bridge.symbol_select(symbol, enable)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "symbol_select",
                "symbol": symbol,
                "enable": enable,
                "result": result,
            },
        )

        if isinstance(result, dict):
            return {"symbol": symbol, **result}
        return {"symbol": symbol, "selected": enable, "success": bool(result)}

    async def order_calc_margin(
        self,
        order_type: str,
        symbol: str,
        volume: float,
        price: float,
    ) -> dict[str, Any]:
        """Calculate margin required for order without executing."""
        result = await self.bridge.order_calc_margin(order_type, symbol, volume, price)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "order_calc_margin",
                "symbol": symbol,
                "volume": volume,
            },
        )

        if result is None:
            return {"margin": None, "currency": None}

        return {
            "margin": result.get("margin", 0),
            "currency": result.get("currency", ""),
            "symbol": symbol,
            "volume": volume,
        }

    async def order_calc_profit(
        self,
        order_type: str,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> dict[str, Any]:
        """Calculate projected profit without executing."""
        result = await self.bridge.order_calc_profit(
            order_type, symbol, volume, price_open, price_close
        )

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "order_calc_profit",
                "symbol": symbol,
                "volume": volume,
            },
        )

        if result is None:
            return {"profit": None, "currency": None, "pips": 0}

        tick_size = await self.bridge.symbol_info(symbol)
        point = tick_size.get("point", 0.00001) if tick_size else 0.00001

        digits = tick_size.get("digits", 5) if tick_size else 5
        pip_multiplier = 10 if digits == 5 else 1
        pips = abs(price_close - price_open) / point / pip_multiplier if point > 0 else 0

        return {
            "profit": result.get("profit", 0),
            "currency": result.get("currency", ""),
            "symbol": symbol,
            "volume": volume,
            "pips": round(pips, 1),
        }

    async def order_check(
        self,
        symbol: str,
        volume: float,
        order_type: str,
        price: float,
        sl: float | None = None,
        tp: float | None = None,
    ) -> dict[str, Any]:
        """Validate order request without executing (dry run)."""
        result = await self.bridge.order_check(symbol, order_type, volume, price, sl or 0, tp or 0)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "order_check",
                "symbol": symbol,
                "volume": volume,
                "order_type": order_type,
            },
        )

        return {
            "retcode": result.get("retcode", -1),
            "retcode_description": result.get("comment", ""),
            "balance": result.get("balance", 0.0),
            "equity": result.get("equity", 0.0),
            "profit": result.get("profit", 0.0),
            "margin": result.get("margin", 0.0),
            "margin_free": result.get("margin_free", 0.0),
            "margin_level": result.get("margin_level", 0.0),
            "comment": result.get("comment", ""),
        }


async def handle_terminal_get_info(
    service: TerminalMgmtService,
    args: dict,
) -> dict[str, Any]:
    result = await service.get_terminal_info()
    return result.model_dump()


async def handle_terminal_get_data_path(
    service: TerminalMgmtService,
    args: dict,
) -> dict[str, Any]:
    result = await service.get_terminal_info()
    return {"data_path": result.data_path}


async def handle_terminal_get_common_path(
    service: TerminalMgmtService,
    args: dict,
) -> dict[str, Any]:
    result = await service.get_terminal_info()
    return {
        "common_path": result.path.replace("\\MetaTrader 5\\", "\\MetaTrader 5 MQL5\\").rsplit(
            "\\", 1
        )[0]
        + "\\MetaTrader 5"
    }


async def handle_symbol_select(
    service: TerminalMgmtService,
    args: dict,
) -> dict[str, Any]:
    inp = SymbolSelectInput.model_validate(args)
    return await service.symbol_select(inp.symbol, inp.enable)


async def handle_order_calc_margin(
    service: TerminalMgmtService,
    args: dict,
) -> dict[str, Any]:
    inp = OrderCalcMarginInput.model_validate(args)
    return await service.order_calc_margin(
        order_type=inp.order_type,
        symbol=inp.symbol,
        volume=inp.volume,
        price=inp.price,
    )


async def handle_order_calc_profit(
    service: TerminalMgmtService,
    args: dict,
) -> dict[str, Any]:
    from pydantic import BaseModel

    class OrderCalcProfitInput(BaseModel):
        order_type: str
        symbol: str
        volume: float
        price_open: float
        price_close: float

    inp = OrderCalcProfitInput.model_validate(args)
    return await service.order_calc_profit(
        order_type=inp.order_type,
        symbol=inp.symbol,
        volume=inp.volume,
        price_open=inp.price_open,
        price_close=inp.price_close,
    )


async def handle_order_check(
    service: TerminalMgmtService,
    args: dict,
) -> dict[str, Any]:
    from pydantic import BaseModel

    class OrderCheckInput(BaseModel):
        symbol: str
        volume: float
        order_type: str
        price: float = 0
        sl: float = 0
        tp: float = 0

    inp = OrderCheckInput.model_validate(args)
    return await service.order_check(
        symbol=inp.symbol,
        volume=inp.volume,
        order_type=inp.order_type,
        price=inp.price,
        sl=inp.sl,
        tp=inp.tp,
    )
