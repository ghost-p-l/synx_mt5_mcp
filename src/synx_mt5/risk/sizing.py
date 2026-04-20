"""Position sizing engine - Calculates safe position sizes based on risk limits."""

from synx_mt5.risk.preflight import OrderRequest


class PositionSizingEngine:
    """Calculates position sizes respecting risk limits."""

    def __init__(self, config: dict):
        self.max_risk_per_trade_pct = config.get("max_risk_per_trade_pct", 1.0)
        self.max_total_exposure_pct = config.get("max_total_exposure_pct", 10.0)
        self.max_positions_per_symbol = config.get("max_positions_per_symbol", 3)
        self.max_total_positions = config.get("max_total_positions", 10)

    async def check_and_cap_volume(
        self, req: OrderRequest, account: dict, positions: list, symbol_info: dict
    ) -> tuple[float, list[str]]:
        """Check position sizing and cap if needed."""
        equity = account.get("equity", 0)
        warnings = []

        if len(positions) >= self.max_total_positions:
            raise ValueError(f"Max positions ({self.max_total_positions}) reached")

        symbol_positions = [p for p in positions if p.get("symbol") == req.symbol]
        if len(symbol_positions) >= self.max_positions_per_symbol:
            raise ValueError(
                f"Max positions for {req.symbol} ({self.max_positions_per_symbol}) reached"
            )

        tick_value = symbol_info.get("trade_tick_value", 10)
        tick_size = symbol_info.get("trade_tick_size", 0.0001)

        if req.sl is not None and tick_value > 0:
            price = req.price if req.price > 0 else symbol_info.get("ask", 0)
            sl_distance = abs(price - req.sl) / tick_size
            risk_per_lot = sl_distance * tick_value
            max_risk_amount = equity * (self.max_risk_per_trade_pct / 100)
            max_volume_by_risk = max_risk_amount / risk_per_lot if risk_per_lot > 0 else req.volume

            if req.volume > max_volume_by_risk:
                capped = round(max_volume_by_risk, 2)
                warnings.append(
                    f"Volume capped from {req.volume} to {capped} "
                    f"to stay within {self.max_risk_per_trade_pct}% risk"
                )
                return capped, warnings

        return req.volume, warnings
