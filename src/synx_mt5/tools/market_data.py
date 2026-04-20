"""Market Data Tools - Symbol information and OHLCV/tick data retrieval."""

from datetime import datetime
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field, field_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType
from synx_mt5.security.injection_shield import sanitise_dict, sanitise_string
from synx_mt5.security.rate_limiter import RateLimiter

log = structlog.get_logger(__name__)

TimeframeLiteral = Literal[
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
    "M6",
    "M10",
    "M12",
    "M15",
    "M20",
    "M30",
    "H1",
    "H2",
    "H3",
    "H4",
    "H6",
    "H8",
    "H12",
    "D1",
    "W1",
    "MN1",
]

VALID_TIMEFRAMES = {
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
    "M6",
    "M10",
    "M12",
    "M15",
    "M20",
    "M30",
    "H1",
    "H2",
    "H3",
    "H4",
    "H6",
    "H8",
    "H12",
    "D1",
    "W1",
    "MN1",
}

TickFlagsLiteral = Literal["COPY_TICKS_ALL", "COPY_TICKS_INFO", "COPY_TICKS_TRADE"]
VALID_TICK_FLAGS = {"COPY_TICKS_ALL", "COPY_TICKS_INFO", "COPY_TICKS_TRADE"}


class GetSymbolsInput(BaseModel):
    """Input for get_symbols tool."""

    group: str | None = Field(
        default=None, description="Symbol group filter pattern (e.g. '*USD*', 'Forex*')"
    )
    exact_match: bool = Field(
        default=False, description="If true, group is exact match instead of pattern"
    )

    @field_validator("group")
    @classmethod
    def sanitize_group(cls, v: str | None) -> str | None:
        if v is None:
            return None
        sanitized = sanitise_string(v, "get_symbols:group")
        if len(sanitized) > 64:
            raise ValueError("Group pattern exceeds 64 characters")
        return sanitized


class SymbolInfo(BaseModel):
    """Symbol information output."""

    name: str
    description: str
    path: str
    digits: int
    trade_mode: int
    bid: float
    ask: float
    spread: int
    volume_min: float
    volume_max: float
    volume_step: float
    point: float
    tick_value: float
    tick_size: float


class GetSymbolsOutput(BaseModel):
    """Output for get_symbols tool."""

    count: int
    symbols: list[dict[str, Any]]
    group_filter: str | None = None


class GetSymbolInfoInput(BaseModel):
    """Input for get_symbol_info tool."""

    symbol: str = Field(min_length=1, max_length=32)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "symbol").upper()


class GetSymbolInfoTickInput(BaseModel):
    """Input for get_symbol_info_tick tool."""

    symbol: str = Field(min_length=1, max_length=32)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "symbol").upper()


class GetSymbolsTotalInput(BaseModel):
    """Input for get_symbols_total tool."""

    pass


class CopyRatesFromPosInput(BaseModel):
    """Input for copy_rates_from_pos tool."""

    symbol: str = Field(min_length=1, max_length=32)
    timeframe: TimeframeLiteral
    start_pos: int = Field(ge=0, le=1000000)
    count: int = Field(ge=1, le=100000)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "copy_rates_from_pos:symbol")

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        if v not in VALID_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {v}")
        return v


class CopyRatesFromInput(BaseModel):
    """Input for copy_rates_from tool."""

    symbol: str = Field(min_length=1, max_length=32)
    timeframe: TimeframeLiteral
    date_from: str = Field(description="ISO 8601 datetime")
    count: int = Field(ge=1, le=100000)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "copy_rates_from:symbol")

    @field_validator("date_from")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid datetime format: {v}") from e
        sanitized = sanitise_string(v, "copy_rates_from:date_from")
        return sanitized


class CopyRatesRangeInput(BaseModel):
    """Input for copy_rates_range tool."""

    symbol: str = Field(min_length=1, max_length=32)
    timeframe: TimeframeLiteral
    date_from: str
    date_to: str

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "copy_rates_range:symbol")

    @field_validator("date_from", "date_to")
    @classmethod
    def validate_dates(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid datetime format: {v}") from e
        return sanitise_string(v, "copy_rates_range:date")


class CopyTicksFromInput(BaseModel):
    """Input for copy_ticks_from tool."""

    symbol: str = Field(min_length=1, max_length=32)
    date_from: str
    count: int = Field(ge=1, le=1000000)
    flags: TickFlagsLiteral = "COPY_TICKS_ALL"

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "copy_ticks_from:symbol")


class CopyTicksRangeInput(BaseModel):
    """Input for copy_ticks_range tool."""

    symbol: str = Field(min_length=1, max_length=32)
    date_from: str
    date_to: str
    flags: TickFlagsLiteral = "COPY_TICKS_ALL"

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "copy_ticks_range:symbol")


class MarketDataService:
    """
    Service layer for market data operations.

    Responsibilities:
    - Bridge communication
    - Rate limiting
    - Output sanitization
    - Error translation
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
        rate_limiter: RateLimiter | None = None,
    ):
        self.bridge = bridge
        self.audit = audit
        self.rate_limiter = rate_limiter or RateLimiter({})

    def _check_rate_limit(self, tool_name: str) -> bool:
        """Check rate limit for tool."""
        if self.rate_limiter and not self.rate_limiter.check(tool_name):
            log.warning("rate_limit_exceeded", tool=tool_name)
            raise PermissionError(f"Rate limit exceeded for {tool_name}")
        return True

    def _sanitize_symbol_info(self, data: dict) -> dict:
        """Sanitize symbol info output."""
        return sanitise_dict(data, "symbol_info")

    async def get_symbols(
        self,
        group: str | None = None,
        exact_match: bool = False,
    ) -> GetSymbolsOutput:
        """Get symbols matching filter."""
        try:
            if group and not exact_match:
                symbols = await self.bridge.symbols_get(group)
            else:
                symbols = await self.bridge.symbols_get()

            sanitized = [self._sanitize_symbol_info(s) for s in symbols]

            self.audit.log(
                AuditEventType.TOOL_INVOCATION,
                {
                    "tool": "get_symbols",
                    "group": group,
                    "count": len(sanitized),
                },
            )

            return GetSymbolsOutput(
                count=len(sanitized),
                symbols=sanitized,
                group_filter=group,
            )

        except Exception as e:
            log.error("get_symbols_failed", error=str(e))
            raise

    async def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        """Get full symbol contract specification."""
        self._check_rate_limit("get_symbol_info")

        info = await self.bridge.symbol_info(symbol)
        if info is None:
            log.warning("symbol_not_found", symbol=symbol)
            return None

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_symbol_info",
                "symbol": symbol,
            },
        )

        return SymbolInfo(
            name=info.get("name", symbol),
            description=info.get("description", ""),
            path=info.get("path", ""),
            digits=info.get("digits", 5),
            trade_mode=info.get("trade_mode", 0),
            bid=info.get("bid", 0.0),
            ask=info.get("ask", 0.0),
            spread=info.get("spread", 0),
            volume_min=info.get("volume_min", 0.01),
            volume_max=info.get("volume_max", 100.0),
            volume_step=info.get("volume_step", 0.01),
            point=info.get("point", 0.00001),
            tick_value=info.get("trade_tick_value", 10.0),
            tick_size=info.get("trade_tick_size", 0.00001),
        )

    async def get_symbol_info_tick(self, symbol: str) -> dict[str, Any]:
        """Get current tick data for symbol."""
        self._check_rate_limit("get_symbol_info_tick")

        tick = await self.bridge.symbol_info_tick(symbol)
        if tick is None:
            return {}

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_symbol_info_tick",
                "symbol": symbol,
            },
        )

        return sanitise_dict(tick, "tick")

    async def get_symbols_total(self) -> dict[str, Any]:
        """Get total count of available symbols."""
        total = await self.bridge.symbols_total()

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_symbols_total",
            },
        )

        return {"total": total}

    async def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: str,
        start_pos: int,
        count: int,
    ) -> dict[str, Any]:
        """Copy OHLCV bars from position offset."""
        self._check_rate_limit("copy_rates_from_pos")

        rates = await self.bridge.copy_rates_from_pos(symbol, timeframe, start_pos, count)

        sanitized = [sanitise_dict(r, f"rates[{i}]") for i, r in enumerate(rates)]

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "copy_rates_from_pos",
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(sanitized),
            },
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "rates": sanitized,
            "count": len(sanitized),
        }

    async def copy_rates_from(
        self,
        symbol: str,
        timeframe: str,
        date_from: str,
        count: int,
    ) -> dict[str, Any]:
        """Copy OHLCV bars from datetime."""
        self._check_rate_limit("copy_rates_from")

        rates = await self.bridge.copy_rates_from(symbol, timeframe, date_from, count)

        sanitized = [sanitise_dict(r, f"rates[{i}]") for i, r in enumerate(rates)]

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "copy_rates_from",
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(sanitized),
            },
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "rates": sanitized,
            "count": len(sanitized),
        }

    async def copy_rates_range(
        self,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        """Copy OHLCV bars in datetime range."""
        rates = await self.bridge.copy_rates_range(symbol, timeframe, date_from, date_to)

        sanitized = [sanitise_dict(r, f"rates[{i}]") for i, r in enumerate(rates)]

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "copy_rates_range",
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(sanitized),
            },
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "rates": sanitized,
            "count": len(sanitized),
        }

    async def copy_ticks_from(
        self,
        symbol: str,
        date_from: str,
        count: int,
        flags: str = "COPY_TICKS_ALL",
    ) -> dict[str, Any]:
        """Copy raw tick data from datetime."""
        self._check_rate_limit("copy_ticks_from")

        if flags not in VALID_TICK_FLAGS:
            raise ValueError(f"Invalid tick flags: {flags}")

        ticks = await self.bridge.copy_ticks_from(symbol, date_from, count, flags)

        sanitized = [sanitise_dict(t, f"ticks[{i}]") for i, t in enumerate(ticks)]

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "copy_ticks_from",
                "symbol": symbol,
                "count": len(sanitized),
                "flags": flags,
            },
        )

        return {
            "symbol": symbol,
            "ticks": sanitized,
            "count": len(sanitized),
            "flags": flags,
        }

    async def copy_ticks_range(
        self,
        symbol: str,
        date_from: str,
        date_to: str,
        flags: str = "COPY_TICKS_ALL",
    ) -> dict[str, Any]:
        """Copy raw tick data in datetime range."""
        self._check_rate_limit("copy_ticks_range")

        ticks = await self.bridge.copy_ticks_range(symbol, date_from, date_to, flags)

        sanitized = [sanitise_dict(t, f"ticks[{i}]") for i, t in enumerate(ticks)]

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "copy_ticks_range",
                "symbol": symbol,
                "count": len(sanitized),
                "flags": flags,
            },
        )

        return {
            "symbol": symbol,
            "ticks": sanitized,
            "count": len(sanitized),
            "flags": flags,
        }

    async def symbol_select(self, symbol: str, select: bool = True) -> dict[str, Any]:
        """Select or deselect a symbol in Market Watch."""
        self._check_rate_limit("symbol_select")

        result = await self.bridge.symbol_select(symbol, select)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "symbol_select",
                "symbol": symbol,
                "select": select,
            },
        )

        return {"symbol": symbol, "select": select, "result": result}


async def handle_get_symbols(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    inp = GetSymbolsInput.model_validate(args)
    result = await service.get_symbols(group=inp.group, exact_match=inp.exact_match)
    return result.model_dump()


async def handle_get_symbol_info(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    inp = GetSymbolInfoInput.model_validate(args)
    result = await service.get_symbol_info(inp.symbol)
    return result.model_dump() if result else {"error": "Symbol not found"}


async def handle_get_symbol_info_tick(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    inp = GetSymbolInfoTickInput.model_validate(args)
    result = await service.get_symbol_info_tick(inp.symbol)
    return result


async def handle_get_symbols_total(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    return await service.get_symbols_total()


async def handle_copy_rates_from_pos(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    inp = CopyRatesFromPosInput.model_validate(args)
    return await service.copy_rates_from_pos(
        symbol=inp.symbol,
        timeframe=inp.timeframe,
        start_pos=inp.start_pos,
        count=inp.count,
    )


async def handle_copy_rates_from(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    inp = CopyRatesFromInput.model_validate(args)
    return await service.copy_rates_from(
        symbol=inp.symbol,
        timeframe=inp.timeframe,
        date_from=inp.date_from,
        count=inp.count,
    )


async def handle_copy_rates_range(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    inp = CopyRatesRangeInput.model_validate(args)
    return await service.copy_rates_range(
        symbol=inp.symbol,
        timeframe=inp.timeframe,
        date_from=inp.date_from,
        date_to=inp.date_to,
    )


async def handle_copy_ticks_from(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    inp = CopyTicksFromInput.model_validate(args)
    return await service.copy_ticks_from(
        symbol=inp.symbol,
        date_from=inp.date_from,
        count=inp.count,
        flags=inp.flags,
    )


async def handle_copy_ticks_range(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    inp = CopyTicksRangeInput.model_validate(args)
    return await service.copy_ticks_range(
        symbol=inp.symbol,
        date_from=inp.date_from,
        date_to=inp.date_to,
        flags=inp.flags,
    )


async def handle_symbol_select(
    service: MarketDataService,
    args: dict,
) -> dict[str, Any]:
    inp = GetSymbolInfoInput.model_validate(args)
    symbol = inp.symbol
    select = args.get("select", True)
    return await service.symbol_select(symbol, select)
