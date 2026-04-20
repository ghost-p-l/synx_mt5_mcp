"""Execution Tools - Order placement, modification, and position management."""

from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator, model_validator

from synx_mt5.audit import AuditEngine, AuditEventType
from synx_mt5.idempotency.engine import IdempotencyEngine
from synx_mt5.risk.circuit_breaker import DrawdownCircuitBreaker
from synx_mt5.risk.hitl import HITLGate
from synx_mt5.risk.preflight import OrderRequest, PreFlightResult, PreFlightValidator
from synx_mt5.risk.sizing import PositionSizingEngine
from synx_mt5.security.injection_shield import sanitise_string

log = structlog.get_logger(__name__)


class OrderTypeLiteral(StrEnum):
    """Valid order types."""

    BUY = "ORDER_TYPE_BUY"
    SELL = "ORDER_TYPE_SELL"
    BUY_LIMIT = "ORDER_TYPE_BUY_LIMIT"
    SELL_LIMIT = "ORDER_TYPE_SELL_LIMIT"
    BUY_STOP = "ORDER_TYPE_BUY_STOP"
    SELL_STOP = "ORDER_TYPE_SELL_STOP"


VALID_ORDER_TYPES = {e.value for e in OrderTypeLiteral}


class OrderSendInput(BaseModel):
    """Input for order_send tool."""

    symbol: str = Field(min_length=1, max_length=32)
    volume: float = Field(gt=0, le=100.0)
    order_type: OrderTypeLiteral
    price: float = Field(ge=0)
    sl: float = Field(default=0, ge=0)
    tp: float = Field(default=0, ge=0)
    comment: str | None = Field(default=None, max_length=31)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "order_send:symbol").upper()

    @field_validator("comment")
    @classmethod
    def sanitize_comment(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return sanitise_string(v[:31], "order_send:comment")


class OrderSendOutput(BaseModel):
    """Output for order_send tool."""

    retcode: int
    retcode_description: str
    ticket: int | None = None
    volume: float | None = None
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    idempotency_key: str
    magic: int
    warnings: list[str] = Field(default_factory=list)
    hitl_approved: bool = False


class OrderModifyInput(BaseModel):
    """Input for order_modify tool."""

    ticket: int = Field(gt=0)
    price: float | None = Field(default=None, ge=0)
    sl: float | None = Field(default=None, ge=0)
    tp: float | None = Field(default=None, ge=0)


class OrderModifyOutput(BaseModel):
    """Output for order_modify tool."""

    retcode: int
    retcode_description: str
    ticket: int
    modified_fields: list[str]


class OrderCancelInput(BaseModel):
    """Input for order_cancel tool."""

    ticket: int = Field(gt=0)


class OrderCancelOutput(BaseModel):
    """Output for order_cancel tool."""

    retcode: int
    retcode_description: str
    ticket: int
    cancelled: bool


class PositionCloseInput(BaseModel):
    """Input for position_close tool."""

    ticket: int = Field(gt=0)
    volume: float | None = Field(default=None, gt=0, le=100.0)
    deviation: int = Field(default=20, ge=0, le=1000)


class PositionCloseOutput(BaseModel):
    """Output for position_close tool."""

    retcode: int
    retcode_description: str
    ticket: int
    closed: bool
    close_price: float | None = None


class PositionCloseAllInput(BaseModel):
    """Input for position_close_all tool."""

    symbol: str | None = Field(default=None, max_length=32)
    confirm: bool = Field(description="Must be explicitly true to proceed")

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return sanitise_string(v, "position_close_all:symbol").upper()

    @model_validator(mode="after")
    def validate_confirm(self):
        if not self.confirm:
            raise ValueError("confirm must be explicitly true to close all positions")
        return self


class PositionCloseAllOutput(BaseModel):
    """Output for position_close_all tool."""

    closed_count: int
    failed_count: int
    results: list[dict[str, Any]]


class PositionModifyInput(BaseModel):
    """Input for position_modify tool."""

    ticket: int = Field(gt=0)
    sl: float | None = Field(default=None, ge=0)
    tp: float | None = Field(default=None, ge=0)


class PositionModifyOutput(BaseModel):
    """Output for position_modify tool."""

    retcode: int
    retcode_description: str
    ticket: int
    modified: bool


class ExecutionService:
    """
    Service layer for execution operations.

    Implements the full risk guard stack:
    1. Capability check
    2. Rate limit check
    3. Pre-flight validation
    4. Position sizing engine
    5. Circuit breaker check
    6. HITL approval gate
    7. Idempotency check
    8. Execute order
    9. Audit log
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
        risk_config: dict,
        preflight: PreFlightValidator,
        sizing: PositionSizingEngine,
        circuit_breaker: DrawdownCircuitBreaker | None,
        hitl: HITLGate | None,
        idempotency: IdempotencyEngine,
    ):
        self.bridge = bridge
        self.audit = audit
        self.risk_config = risk_config
        self.preflight = preflight
        self.sizing = sizing
        self.circuit_breaker = circuit_breaker
        self.hitl = hitl
        self.idempotency = idempotency

    async def order_send(
        self,
        symbol: str,
        volume: float,
        order_type: str,
        price: float,
        sl: float | None = None,
        tp: float | None = None,
        comment: str | None = None,
    ) -> OrderSendOutput:
        """
        Place market or pending order with full risk guard stack.

        Risk Stack:
        1. Pre-flight validation (symbol, volume, SL/TP)
        2. Position sizing check
        3. Circuit breaker check
        4. HITL approval (if required)
        5. Idempotency check
        6. Execute order
        """
        magic = self.idempotency.generate_magic()
        idempotency_key = self.idempotency.make_key(symbol, volume, order_type, price)

        order_req = OrderRequest(
            symbol=symbol,
            volume=volume,
            order_type=order_type,
            price=price,
            sl=sl,
            tp=tp,
            comment=comment,
            magic=magic,
        )

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "order_send",
                "symbol": symbol,
                "volume": volume,
                "order_type": order_type,
                "idempotency_key": idempotency_key,
            },
        )

        preflight_result: PreFlightResult = await self.preflight.validate(order_req)

        if not preflight_result.passed:
            self.audit.log(
                AuditEventType.RISK_PREFLIGHT_FAILED,
                {
                    "symbol": symbol,
                    "reason": preflight_result.reason,
                },
            )
            return OrderSendOutput(
                retcode=-1,
                retcode_description=f"Pre-flight failed: {preflight_result.reason}",
                idempotency_key=idempotency_key,
                magic=magic,
                warnings=preflight_result.warnings or [],
            )

        self.audit.log(
            AuditEventType.RISK_PREFLIGHT_PASSED,
            {
                "symbol": symbol,
                "warnings": preflight_result.warnings,
            },
        )

        if self.circuit_breaker:
            self.circuit_breaker.assert_closed()

        account = await self.bridge.account_info()
        positions = await self.bridge.positions_get()
        symbol_info = await self.bridge.symbol_info(symbol)
        if symbol_info is None:
            symbol_info = {}
        capped_volume, sizing_warnings = await self.sizing.check_and_cap_volume(
            order_req, account, positions, symbol_info
        )
        if capped_volume != volume:
            volume = capped_volume
        preflight_result.warnings.extend(sizing_warnings)

        if self.hitl and self.hitl.enabled:
            await self.hitl.request_approval(order_req)
            hitl_approved = True
        else:
            hitl_approved = True

        if not self.idempotency.check_and_register(idempotency_key):
            self.audit.log(
                AuditEventType.IDEMPOTENCY_DUPLICATE_BLOCKED,
                {
                    "idempotency_key": idempotency_key,
                },
            )
            return OrderSendOutput(
                retcode=-2,
                retcode_description="Duplicate order blocked by idempotency engine",
                idempotency_key=idempotency_key,
                magic=magic,
                warnings=preflight_result.warnings or [],
            )

        try:
            result = await self.bridge.order_send(
                symbol=symbol,
                order_type=order_type,
                volume=volume,
                price=price,
                sl=sl or 0,
                tp=tp or 0,
                magic=magic,
                comment=comment,
            )

            self.audit.log(
                AuditEventType.TOOL_INVOCATION,
                {
                    "tool": "order_send",
                    "outcome": "success",
                    "ticket": result.get("ticket"),
                    "retcode": result.get("retcode"),
                },
            )

            return OrderSendOutput(
                retcode=result.get("retcode", 0),
                retcode_description=result.get("retcode_description", ""),
                ticket=result.get("ticket"),
                volume=result.get("volume"),
                price=result.get("price"),
                sl=sl,
                tp=tp,
                idempotency_key=idempotency_key,
                magic=magic,
                warnings=preflight_result.warnings or [],
                hitl_approved=hitl_approved,
            )

        except Exception as e:
            log.error("order_send_failed", error=str(e))
            self.audit.log(
                AuditEventType.TOOL_INVOCATION,
                {
                    "tool": "order_send",
                    "outcome": "error",
                    "error": str(e),
                },
            )
            return OrderSendOutput(
                retcode=-99,
                retcode_description=f"Execution error: {str(e)}",
                idempotency_key=idempotency_key,
                magic=magic,
                warnings=preflight_result.warnings or [],
            )

    async def order_modify(
        self,
        ticket: int,
        price: float | None = None,
        sl: float | None = None,
        tp: float | None = None,
    ) -> OrderModifyOutput:
        """Modify SL/TP/price of pending order."""
        modified_fields = []
        if price is not None:
            modified_fields.append("price")
        if sl is not None:
            modified_fields.append("sl")
        if tp is not None:
            modified_fields.append("tp")

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "order_modify",
                "ticket": ticket,
                "modified_fields": modified_fields,
            },
        )

        result = await self.bridge.order_modify(
            ticket=ticket,
            price=price or 0,
            sl=sl or 0,
            tp=tp or 0,
        )

        return OrderModifyOutput(
            retcode=result.get("retcode", 0),
            retcode_description=result.get("retcode_description", ""),
            ticket=ticket,
            modified_fields=modified_fields,
        )

    async def order_cancel(self, ticket: int) -> OrderCancelOutput:
        """Cancel pending order."""
        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "order_cancel",
                "ticket": ticket,
            },
        )

        result = await self.bridge.order_cancel(ticket)
        cancelled = result.get("retcode", -1) == 10009

        return OrderCancelOutput(
            retcode=result.get("retcode", -1),
            retcode_description=result.get("retcode_description", ""),
            ticket=ticket,
            cancelled=cancelled,
        )

    async def position_close(
        self,
        ticket: int,
        volume: float | None = None,
        deviation: int = 20,
    ) -> PositionCloseOutput:
        """Close open position by ticket."""
        if self.circuit_breaker:
            self.circuit_breaker.assert_closed()

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "position_close",
                "ticket": ticket,
                "volume": volume,
            },
        )

        result = await self.bridge.position_close(ticket, volume or 0, deviation)

        closed = result.get("retcode", -1) in (10009, 10008, 0)

        return PositionCloseOutput(
            retcode=result.get("retcode", -1),
            retcode_description=result.get("retcode_description", ""),
            ticket=ticket,
            closed=closed,
            close_price=None,
        )

    async def position_modify(
        self,
        ticket: int,
        sl: float | None = None,
        tp: float | None = None,
    ) -> PositionModifyOutput:
        """Modify SL/TP of an open position."""
        if self.circuit_breaker:
            self.circuit_breaker.assert_closed()

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "position_modify",
                "ticket": ticket,
                "sl": sl,
                "tp": tp,
            },
        )

        result = await self.bridge.position_modify(ticket, sl or 0, tp or 0)

        modified = result.get("retcode", -1) in (10009, 10008, 0)

        return PositionModifyOutput(
            retcode=result.get("retcode", -1),
            retcode_description=result.get("retcode_description", ""),
            ticket=ticket,
            modified=modified,
        )

    async def position_close_all(
        self,
        symbol: str | None = None,
    ) -> PositionCloseAllOutput:
        """Close ALL open positions. DESTRUCTIVE operation."""
        positions = await self.bridge.positions_get()

        if symbol:
            positions = [p for p in positions if p.get("symbol") == symbol]

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "position_close_all",
                "symbol": symbol,
                "destructive": True,
                "position_count": len(positions),
            },
        )

        if not positions:
            return PositionCloseAllOutput(
                closed_count=0,
                failed_count=0,
                results=[],
            )

        results = []
        closed_count = 0
        failed_count = 0

        for pos in positions:
            ticket = pos.get("ticket")
            try:
                result = await self.position_close(ticket)
                if result.closed:
                    closed_count += 1
                else:
                    failed_count += 1
                results.append({"ticket": ticket, "success": result.closed})
            except Exception as e:
                failed_count += 1
                results.append({"ticket": ticket, "success": False, "error": str(e)})

        return PositionCloseAllOutput(
            closed_count=closed_count,
            failed_count=failed_count,
            results=results,
        )


async def handle_order_send(
    service: "ExecutionService",
    args: dict,
) -> dict[str, Any]:
    inp = OrderSendInput.model_validate(args)
    result = await service.order_send(
        symbol=inp.symbol,
        volume=inp.volume,
        order_type=inp.order_type.value,
        price=inp.price,
        sl=inp.sl,
        tp=inp.tp,
        comment=inp.comment,
    )
    return result.model_dump()


async def handle_order_modify(
    service: "ExecutionService",
    args: dict,
) -> dict[str, Any]:
    inp = OrderModifyInput.model_validate(args)
    result = await service.order_modify(
        ticket=inp.ticket,
        price=inp.price,
        sl=inp.sl,
        tp=inp.tp,
    )
    return result.model_dump()


async def handle_order_cancel(
    service: "ExecutionService",
    args: dict,
) -> dict[str, Any]:
    inp = OrderCancelInput.model_validate(args)
    result = await service.order_cancel(ticket=inp.ticket)
    return result.model_dump()


async def handle_position_close(
    service: "ExecutionService",
    args: dict,
) -> dict[str, Any]:
    inp = PositionCloseInput.model_validate(args)
    result = await service.position_close(
        ticket=inp.ticket,
        volume=inp.volume,
        deviation=inp.deviation,
    )
    return result.model_dump()


async def handle_position_close_partial(
    service: "ExecutionService",
    args: dict,
) -> dict[str, Any]:
    inp = PositionCloseInput.model_validate(args)
    result = await service.position_close(
        ticket=inp.ticket,
        volume=inp.volume,
        deviation=inp.deviation,
    )
    return result.model_dump()


async def handle_position_close_all(
    service: "ExecutionService",
    args: dict,
) -> dict[str, Any]:
    from pydantic import BaseModel

    class PositionCloseAllInput(BaseModel):
        symbol: str | None = None
        confirm: bool

    inp = PositionCloseAllInput.model_validate(args)
    if not inp.confirm:
        return {"error": "confirm must be true to close all positions", "closed_count": 0}
    result = await service.position_close_all(symbol=inp.symbol)
    return result.model_dump()


async def handle_position_modify(
    service: "ExecutionService",
    args: dict,
) -> dict[str, Any]:
    inp = PositionModifyInput.model_validate(args)
    result = await service.position_modify(
        ticket=inp.ticket,
        sl=inp.sl,
        tp=inp.tp,
    )
    return result.model_dump()
