"""Market Depth (DOM) Tools - Level 2 order book data."""

from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType
from synx_mt5.security.injection_shield import sanitise_string

log = structlog.get_logger(__name__)


class MarketBookSubscribeInput(BaseModel):
    """Input for market_book_subscribe tool."""

    symbol: str = Field(min_length=1, max_length=32)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "market_book:symbol").upper()


class MarketBookGetInput(BaseModel):
    """Input for market_book_get tool."""

    symbol: str = Field(min_length=1, max_length=32)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "market_book:symbol").upper()


class MarketBookUnsubscribeInput(BaseModel):
    """Input for market_book_unsubscribe tool."""

    symbol: str = Field(min_length=1, max_length=32)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "market_book:symbol").upper()


class MarketBookEntry(BaseModel):
    """Single DOM entry."""

    type: int
    price: float
    volume: int
    volume_dbl: float


class MarketBookOutput(BaseModel):
    """Output for market_book_get tool."""

    symbol: str
    time: str
    bids: list[dict[str, Any]]
    asks: list[dict[str, Any]]
    spread: float
    best_bid: float
    best_ask: float
    bid_depth: int
    ask_depth: int


class MarketDepthService:
    """
    Service layer for market depth (DOM) operations.
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
    ):
        self.bridge = bridge
        self.audit = audit
        self._subscriptions: set[str] = set()

    async def market_book_subscribe(self, symbol: str) -> dict[str, Any]:
        """Subscribe to Level 2 Depth of Market data for symbol."""
        result = await self.bridge.market_book_add(symbol)

        if result:
            self._subscriptions.add(symbol)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "market_book_subscribe",
                "symbol": symbol,
                "subscribed": result,
            },
        )

        return {
            "symbol": symbol,
            "subscribed": result,
        }

    async def market_book_get(self, symbol: str) -> MarketBookOutput | None:
        """Get current DOM snapshot for subscribed symbol."""
        if symbol not in self._subscriptions:
            log.warning("dom_not_subscribed", symbol=symbol)
            return None

        entries = await self.bridge.market_book_get(symbol)

        if entries is None:
            return None

        bids = []
        asks = []

        for entry in entries:
            if entry.get("type") == 0:
                bids.append(
                    {
                        "price": entry.get("price", 0),
                        "volume": entry.get("volume", 0),
                        "volume_dbl": entry.get("volume_dbl", 0.0),
                    }
                )
            else:
                asks.append(
                    {
                        "price": entry.get("price", 0),
                        "volume": entry.get("volume", 0),
                        "volume_dbl": entry.get("volume_dbl", 0.0),
                    }
                )

        best_bid = bids[0]["price"] if bids else 0.0
        best_ask = asks[0]["price"] if asks else 0.0
        spread = best_ask - best_bid if best_bid and best_ask else 0.0

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "market_book_get",
                "symbol": symbol,
                "bid_levels": len(bids),
                "ask_levels": len(asks),
            },
        )

        return MarketBookOutput(
            symbol=symbol,
            time="",
            bids=bids,
            asks=asks,
            spread=round(spread, 5),
            best_bid=best_bid,
            best_ask=best_ask,
            bid_depth=len(bids),
            ask_depth=len(asks),
        )

    async def market_book_unsubscribe(self, symbol: str) -> dict[str, Any]:
        """Release DOM subscription for symbol."""
        result = await self.bridge.market_book_release(symbol)

        if result:
            self._subscriptions.discard(symbol)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "market_book_unsubscribe",
                "symbol": symbol,
                "released": result,
            },
        )

        return {
            "symbol": symbol,
            "released": result,
        }


async def handle_market_book_subscribe(
    service: MarketDepthService,
    args: dict,
) -> dict[str, Any]:
    inp = MarketBookSubscribeInput.model_validate(args)
    return await service.market_book_subscribe(inp.symbol)


async def handle_market_book_get(
    service: MarketDepthService,
    args: dict,
) -> dict[str, Any]:
    inp = MarketBookGetInput.model_validate(args)
    result = await service.market_book_get(inp.symbol)
    if result is None:
        return {"error": "Book not found"}
    return result.model_dump()


async def handle_market_book_unsubscribe(
    service: MarketDepthService,
    args: dict,
) -> dict[str, Any]:
    inp = MarketBookUnsubscribeInput.model_validate(args)
    return await service.market_book_unsubscribe(inp.symbol)
