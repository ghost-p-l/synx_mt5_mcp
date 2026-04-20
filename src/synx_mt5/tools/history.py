"""History & Analytics Tools - Historical orders, deals, and statistics."""

from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType

log = structlog.get_logger(__name__)


class HistoryOrdersGetInput(BaseModel):
    """Input for history_orders_get tool."""

    date_from: str
    date_to: str
    symbol: str | None = Field(default=None, max_length=32)

    @field_validator("date_from", "date_to")
    @classmethod
    def validate_dates(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid datetime format: {v}") from e
        return v


class HistoryOrdersTotalInput(BaseModel):
    """Input for history_orders_total tool."""

    date_from: str
    date_to: str

    @field_validator("date_from", "date_to")
    @classmethod
    def validate_dates(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid datetime format: {v}") from e
        return v


class HistoryDealsGetInput(BaseModel):
    """Input for history_deals_get tool."""

    date_from: str
    date_to: str
    symbol: str | None = Field(default=None, max_length=32)


class HistoryDealsTotalInput(BaseModel):
    """Input for history_deals_total tool."""

    date_from: str
    date_to: str


class TradingStatisticsOutput(BaseModel):
    """Output for get_trading_statistics tool."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    total_profit: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    expected_payoff: float
    max_drawdown: float
    max_drawdown_pct: float
    avg_win: float
    avg_loss: float
    avg_rr_ratio: float
    best_trade: float
    worst_trade: float
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0


class HistoryService:
    """
    Service layer for history and analytics operations.
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
    ):
        self.bridge = bridge
        self.audit = audit

    async def history_orders_get(
        self,
        date_from: str,
        date_to: str,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """Get historical orders within date range."""
        orders = await self.bridge.history_orders_get(date_from, date_to, symbol or "")

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "history_orders_get",
                "count": len(orders),
                "date_from": date_from,
                "date_to": date_to,
            },
        )

        return {
            "count": len(orders),
            "orders": orders,
        }

    async def history_orders_total(
        self,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        """Get count of historical orders."""
        total = await self.bridge.history_orders_total(date_from, date_to)

        return {"total": total}

    async def history_deals_get(
        self,
        date_from: str,
        date_to: str,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """Get historical deals within date range."""
        deals = await self.bridge.history_deals_get(date_from, date_to, symbol or "")

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "history_deals_get",
                "count": len(deals),
            },
        )

        return {
            "count": len(deals),
            "deals": deals,
        }

    async def history_deals_total(
        self,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        """Get count of historical deals."""
        total = await self.bridge.history_deals_total(date_from, date_to)
        return {"total": total}

    async def get_trading_statistics(
        self,
        date_from: str,
        date_to: str,
    ) -> TradingStatisticsOutput:
        """Compute comprehensive trading statistics."""
        deals_result = await self.history_deals_get(date_from, date_to)
        deals = deals_result["deals"]

        if not deals:
            return TradingStatisticsOutput(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate_pct=0.0,
                total_profit=0.0,
                gross_profit=0.0,
                gross_loss=0.0,
                profit_factor=0.0,
                expected_payoff=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                avg_rr_ratio=0.0,
                best_trade=0.0,
                worst_trade=0.0,
            )

        profits = [d.get("profit", 0) for d in deals]
        winning = [p for p in profits if p > 0]
        losing = [p for p in profits if p < 0]

        total_trades = len(profits)
        winning_trades = len(winning)
        losing_trades = len(losing)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        gross_profit = sum(winning)
        gross_loss = abs(sum(losing))
        total_profit = sum(profits)

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        expected_payoff = total_profit / total_trades if total_trades > 0 else 0

        avg_win = sum(winning) / winning_trades if winning_trades > 0 else 0
        avg_loss = abs(sum(losing)) / losing_trades if losing_trades > 0 else 0
        avg_rr = avg_win / avg_loss if avg_loss > 0 else 0

        best_trade = max(profits) if profits else 0
        worst_trade = min(profits) if profits else 0

        peak = 0
        max_drawdown = 0
        running = 0

        for p in profits:
            running += p
            peak = max(peak, running)
            dd = peak - running
            max_drawdown = max(max_drawdown, dd)

        initial_balance = 10000.0
        max_dd_pct = (max_drawdown / initial_balance * 100) if initial_balance > 0 else 0

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_trading_statistics",
                "total_trades": total_trades,
                "win_rate": round(win_rate, 2),
            },
        )

        return TradingStatisticsOutput(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=round(win_rate, 2),
            total_profit=round(total_profit, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            profit_factor=round(profit_factor, 2),
            expected_payoff=round(expected_payoff, 2),
            max_drawdown=round(max_drawdown, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            avg_rr_ratio=round(avg_rr, 2),
            best_trade=round(best_trade, 2),
            worst_trade=round(worst_trade, 2),
        )


async def handle_history_orders_get(
    service: HistoryService,
    args: dict,
) -> dict[str, Any]:
    inp = HistoryOrdersGetInput.model_validate(args)
    return await service.history_orders_get(
        date_from=inp.date_from,
        date_to=inp.date_to,
        symbol=inp.symbol,
    )


async def handle_history_orders_total(
    service: HistoryService,
    args: dict,
) -> dict[str, Any]:
    inp = HistoryOrdersTotalInput.model_validate(args)
    return await service.history_orders_total(date_from=inp.date_from, date_to=inp.date_to)


async def handle_history_deals_get(
    service: HistoryService,
    args: dict,
) -> dict[str, Any]:
    inp = HistoryDealsGetInput.model_validate(args)
    return await service.history_deals_get(
        date_from=inp.date_from,
        date_to=inp.date_to,
        symbol=inp.symbol,
    )


async def handle_history_deals_total(
    service: HistoryService,
    args: dict,
) -> dict[str, Any]:
    inp = HistoryDealsTotalInput.model_validate(args)
    return await service.history_deals_total(date_from=inp.date_from, date_to=inp.date_to)


async def handle_get_trading_statistics(
    service: HistoryService,
    args: dict,
) -> dict[str, Any]:
    from pydantic import BaseModel

    class StatsInput(BaseModel):
        date_from: str
        date_to: str

    inp = StatsInput.model_validate(args)
    result = await service.get_trading_statistics(date_from=inp.date_from, date_to=inp.date_to)
    return result.model_dump()
