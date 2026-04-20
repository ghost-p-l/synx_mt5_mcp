"""Position Management Tools - Account info, positions, and orders."""

from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType
from synx_mt5.security.injection_shield import sanitise_dict

log = structlog.get_logger(__name__)


class AccountInfoOutput(BaseModel):
    """Output for account_info tool."""

    login: int | None = None
    server: str | None = None
    currency: str | None = None
    company: str | None = None
    balance: float | None = None
    equity: float | None = None
    profit: float | None = None
    margin: float | None = None
    margin_free: float | None = None
    margin_level: float | None = None
    leverage: int | None = None
    trade_mode: int | None = None
    trade_allowed: bool | None = None


class PositionsGetInput(BaseModel):
    """Input for positions_get tool."""

    symbol: str | None = Field(default=None, max_length=32)
    ticket: int | None = Field(default=None, gt=0)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v


class PositionsTotalInput(BaseModel):
    """Input for positions_total tool."""

    pass


class OrdersGetInput(BaseModel):
    """Input for orders_get tool."""

    symbol: str | None = Field(default=None, max_length=32)
    ticket: int | None = Field(default=None, gt=0)


class OrdersTotalInput(BaseModel):
    """Input for orders_total tool."""

    pass


class PositionManagementService:
    """
    Service layer for position and order management.
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
    ):
        self.bridge = bridge
        self.audit = audit

    async def account_info(self) -> AccountInfoOutput:
        """Get full account information."""
        info = await self.bridge.account_info()

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "account_info",
            },
        )

        if not info or info.get("login") is None:
            raise ValueError("Failed to retrieve account info - MT5 may be disconnected")

        return AccountInfoOutput(
            login=info.get("login"),
            server=info.get("server"),
            currency=info.get("currency"),
            company=info.get("company"),
            balance=info.get("balance"),
            equity=info.get("equity"),
            profit=info.get("profit"),
            margin=info.get("margin"),
            margin_free=info.get("margin_free"),
            margin_level=info.get("margin_level"),
            leverage=info.get("leverage"),
            trade_mode=info.get("trade_mode"),
            trade_allowed=info.get("trade_allowed"),
        )

    async def positions_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> dict[str, Any]:
        """Get open positions with optional filtering."""
        positions = await self.bridge.positions_get(symbol or "", ticket or 0)

        sanitized = []
        for pos in positions:
            safe_pos = sanitise_dict(pos, f"position:{pos.get('ticket', 'unknown')}")
            if "comment" in safe_pos:
                safe_pos["comment"] = str(safe_pos["comment"])[:64]
            sanitized.append(safe_pos)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "positions_get",
                "count": len(sanitized),
                "symbol_filter": symbol,
                "ticket_filter": ticket,
            },
        )

        return {
            "count": len(sanitized),
            "positions": sanitized,
        }

    async def positions_total(self) -> dict[str, Any]:
        """Get total count of open positions."""
        result = await self.positions_get()
        total = result["count"]

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "positions_total",
            },
        )

        return {"total": total}

    async def orders_get(
        self,
        symbol: str | None = None,
        ticket: int | None = None,
    ) -> dict[str, Any]:
        """Get pending orders with optional filtering."""
        orders = await self.bridge.orders_get(symbol or "", ticket or 0)

        sanitized = []
        for order in orders:
            safe_order = sanitise_dict(order, f"order:{order.get('ticket', 'unknown')}")
            if "comment" in safe_order:
                safe_order["comment"] = str(safe_order["comment"])[:64]
            sanitized.append(safe_order)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "orders_get",
                "count": len(sanitized),
            },
        )

        return {
            "count": len(sanitized),
            "orders": sanitized,
        }

    async def orders_total(self) -> dict[str, Any]:
        """Get total count of pending orders."""
        result = await self.orders_get()
        total = result["count"]

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "orders_total",
            },
        )

        return {"total": total}


async def handle_account_info(
    service: PositionManagementService,
    args: dict,
) -> dict[str, Any]:
    result = await service.account_info()
    return result.model_dump()


async def handle_get_terminal_info(
    service: PositionManagementService,
    args: dict,
) -> dict[str, Any]:
    info = await service.bridge.terminal_info()
    return info if isinstance(info, dict) else {}


async def handle_positions_get(
    service: PositionManagementService,
    args: dict,
) -> dict[str, Any]:
    symbol = args.get("symbol")
    ticket = args.get("ticket")
    return await service.positions_get(symbol=symbol, ticket=ticket)


async def handle_positions_total(
    service: PositionManagementService,
    args: dict,
) -> dict[str, Any]:
    return await service.positions_total()


async def handle_orders_get(
    service: PositionManagementService,
    args: dict,
) -> dict[str, Any]:
    symbol = args.get("symbol")
    ticket = args.get("ticket")
    return await service.orders_get(symbol=symbol, ticket=ticket)


async def handle_orders_total(
    service: PositionManagementService,
    args: dict,
) -> dict[str, Any]:
    return await service.orders_total()
