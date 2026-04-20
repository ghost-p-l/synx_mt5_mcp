"""Pre-flight validator - Validates orders before execution."""

from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)


@dataclass
class OrderRequest:
    """Order request data."""

    symbol: str
    volume: float
    order_type: str
    price: float
    sl: float | None = None
    tp: float | None = None
    comment: str | None = None
    magic: int = 0


@dataclass
class PreFlightResult:
    """Pre-flight validation result."""

    passed: bool
    reason: str | None = None
    warnings: list[str] | None = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class PreFlightValidator:
    """Validates orders before they reach MT5."""

    def __init__(self, config: dict, bridge):
        self.config = config
        self.bridge = bridge

    async def validate(self, req: OrderRequest) -> PreFlightResult:
        """Run all pre-flight checks."""
        warnings = []

        info = await self.bridge.symbol_info(req.symbol)
        if info is None:
            return PreFlightResult(False, f"Symbol '{req.symbol}' not found")

        trade_mode = info.get("trade_mode", 0)
        if trade_mode not in (1, 2, 4):
            return PreFlightResult(
                False, f"Symbol '{req.symbol}' not currently tradeable (mode={trade_mode})"
            )

        min_vol = info.get("volume_min", 0.01)
        max_vol = info.get("volume_max", 100.0)

        if req.volume < min_vol:
            return PreFlightResult(False, f"Volume {req.volume} below minimum {min_vol}")
        if req.volume > max_vol:
            return PreFlightResult(False, f"Volume {req.volume} exceeds maximum {max_vol}")

        account = await self.bridge.account_info()
        is_demo = account.get("trade_mode", -1) == 0

        if not is_demo and req.sl is None and self.config.get("require_sl", True):
            return PreFlightResult(False, "Stop loss required for live accounts")

        if req.sl is not None:
            tick = await self.bridge.symbol_info_tick(req.symbol)
            current = tick.get("ask") if "BUY" in req.order_type else tick.get("bid")
            point = info.get("point", 0.00001)
            sl_distance_pips = abs(current - req.sl) / point
            min_sl_pips = self.config.get("min_sl_pips", 5)

            if sl_distance_pips < min_sl_pips:
                return PreFlightResult(
                    False, f"SL distance {sl_distance_pips:.1f} pips below minimum {min_sl_pips}"
                )

        if req.comment and len(req.comment) > 31:
            req.comment = req.comment[:31]
            warnings.append("Comment truncated to 31 chars (MT5 limit)")

        if req.sl is not None and req.tp is not None:
            tick = await self.bridge.symbol_info_tick(req.symbol)
            current = tick.get("ask") if "BUY" in req.order_type else tick.get("bid")
            risk = abs(current - req.sl)
            reward = abs(req.tp - current)
            min_rr = self.config.get("min_rr_ratio", 1.0)

            if risk > 0 and (reward / risk) < min_rr:
                warnings.append(f"R:R ratio {reward / risk:.2f}:1 below recommended {min_rr}:1")

        return PreFlightResult(True, warnings=warnings)
