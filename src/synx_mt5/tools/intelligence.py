"""Intelligence Tools - Market regime, correlation, strategy context, and agent memory."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType
from synx_mt5.intelligence.correlation import CorrelationTracker
from synx_mt5.intelligence.memory import AgentMemory
from synx_mt5.intelligence.regime import MarketRegimeDetector
from synx_mt5.intelligence.strategy_context import StrategyContextEngine
from synx_mt5.security.injection_shield import sanitise_string

log = structlog.get_logger(__name__)


class GetMarketRegimeInput(BaseModel):
    """Input for get_market_regime tool."""

    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="H1", pattern="^(M[1-9]|M1[0-5]|H[1-9]|H1[0-2]|D1|W1|MN1)$")
    lookback_bars: int = Field(default=100, ge=50, le=10000)

    @field_validator("symbol")
    @classmethod
    def sanitize_symbol(cls, v: str) -> str:
        return sanitise_string(v, "get_market_regime:symbol").upper()


class GetMarketRegimeOutput(BaseModel):
    """Output for get_market_regime tool."""

    symbol: str
    timeframe: str
    regime: str
    confidence: float
    description: str
    adx: float
    atr_normalised: float
    price_vs_ema200: str
    volatility_pct: float
    reasoning: str


class GetCorrelationMatrixInput(BaseModel):
    """Input for get_correlation_matrix tool."""

    symbols: list[str] = Field(min_length=2, max_length=20)
    timeframe: str = Field(default="H1")
    lookback_bars: int = Field(default=200, ge=50, le=5000)

    @field_validator("symbols")
    @classmethod
    def sanitize_symbols(cls, v: list[str]) -> list[str]:
        return [sanitise_string(s, "correlation_matrix:symbol").upper() for s in v]


class GetCorrelationMatrixOutput(BaseModel):
    """Output for get_correlation_matrix tool."""

    symbols: list[str]
    matrix: list[list[float]]
    warnings: list[str]
    computed_at: str
    lookback_bars: int


class GetDrawdownAnalysisInput(BaseModel):
    """Input for get_drawdown_analysis tool."""

    lookback_days: int = Field(default=30, ge=1, le=365)


class GetDrawdownAnalysisOutput(BaseModel):
    """Output for get_drawdown_analysis tool."""

    current_drawdown_pct: float
    max_drawdown_pct: float
    max_drawdown_date: str | None
    avg_daily_drawdown_pct: float
    recovery_factor: float
    circuit_breaker_distance_pct: float


class StrategyContextInput(BaseModel):
    """Input for set_strategy_context tool."""

    context: str = Field(max_length=2000)

    @field_validator("context")
    @classmethod
    def sanitize_context(cls, v: str) -> str:
        return sanitise_string(v, "strategy_context")


class StrategyContextOutput(BaseModel):
    """Output for strategy context tools."""

    context: str
    last_updated: str | None
    set_by: str | None


class AgentMemoryInput(BaseModel):
    """Input for set_agent_memory tool."""

    key: str = Field(min_length=1, max_length=64, pattern="^[a-zA-Z][a-zA-Z0-9_]*$")
    value: Any

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        if v.startswith("system_"):
            raise ValueError("Keys cannot start with 'system_'")
        return sanitise_string(v, "agent_memory:key")


class AgentMemoryOutput(BaseModel):
    """Output for agent memory tools."""

    key: str
    value: Any
    created_at: str | None = None
    updated_at: str | None = None
    saved: bool = True


class IntelligenceService:
    """
    Service layer for intelligence operations.

    Integrates:
    - MarketRegimeDetector for regime classification
    - CorrelationTracker for cross-symbol correlation
    - StrategyContextEngine for strategy memo
    - AgentMemory for persistent key-value store
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
        storage_path: Path,
        regime_config: dict | None = None,
        correlation_cache_ttl: int = 300,
    ):
        self.bridge = bridge
        self.audit = audit
        self.storage_path = storage_path

        regime_config = regime_config or {}
        self.regime_detector = MarketRegimeDetector(
            adx_threshold=regime_config.get("adx_threshold", 25.0),
            volatility_high=regime_config.get("volatility_high", 0.005),
            volatility_low=regime_config.get("volatility_low", 0.001),
        )

        self.correlation_tracker = CorrelationTracker(
            bridge=bridge,
            cache_ttl_seconds=correlation_cache_ttl,
        )

        self.strategy_context = StrategyContextEngine(storage_path)
        self.agent_memory = AgentMemory(storage_path)

    async def get_market_regime(
        self,
        symbol: str,
        timeframe: str = "H1",
        lookback_bars: int = 100,
    ) -> GetMarketRegimeOutput:
        """
        Classify market regime for symbol.

        Uses ADX, ATR, and 200 EMA to determine:
        - TRENDING_UP: Strong uptrend
        - TRENDING_DOWN: Strong downtrend
        - RANGING: Low-trend market
        - HIGH_VOLATILITY: Elevated volatility
        - LOW_VOLATILITY: Compressed volatility
        """
        rates = await self.bridge.copy_rates_from_pos(symbol, timeframe, 0, lookback_bars)

        if not rates:
            raise ValueError(f"No rate data available for {symbol}")

        result = self.regime_detector.classify(rates)

        reasoning = self._generate_regime_reasoning(symbol, timeframe, result)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_market_regime",
                "symbol": symbol,
                "regime": result["regime"],
                "confidence": result["confidence"],
            },
        )

        return GetMarketRegimeOutput(
            symbol=symbol,
            timeframe=timeframe,
            regime=result["regime"],
            confidence=result["confidence"],
            description=result.get("description", ""),
            adx=result.get("adx", 0.0),
            atr_normalised=result.get("atr_normalised", 0.0),
            price_vs_ema200=result.get("price_vs_ema200", "unknown"),
            volatility_pct=result.get("volatility_pct", 0.0),
            reasoning=reasoning,
        )

    def _generate_regime_reasoning(
        self,
        symbol: str,
        timeframe: str,
        result: dict,
    ) -> str:
        """Generate human-readable reasoning for regime classification."""
        regime = result["regime"]
        adx = result.get("adx", 0)
        atr_norm = result.get("atr_normalised", 0)

        regime_descriptions = {
            "TRENDING_UP": f"{symbol} on {timeframe} shows strong uptrend. ADX={adx:.1f} indicates trend strength.",
            "TRENDING_DOWN": f"{symbol} on {timeframe} shows strong downtrend. ADX={adx:.1f} indicates trend strength.",
            "RANGING": f"{symbol} on {timeframe} is ranging. ADX={adx:.1f} below trend threshold.",
            "HIGH_VOLATILITY": f"{symbol} on {timeframe} shows elevated volatility. ATR={atr_norm:.4f} above threshold.",
            "LOW_VOLATILITY": f"{symbol} on {timeframe} shows compressed volatility. Potential breakout setup.",
        }
        return regime_descriptions.get(
            regime,
            f"Insufficient data for {symbol} regime classification.",
        )

    async def get_correlation_matrix(
        self,
        symbols: list[str],
        timeframe: str = "H1",
        lookback_bars: int = 200,
    ) -> GetCorrelationMatrixOutput:
        """
        Calculate Pearson correlation matrix across symbols.

        Caches results for 5 minutes to reduce computation.
        Warns when correlation >= 0.75 (high correlation risk).
        """
        result = await self.correlation_tracker.get_matrix(
            symbols=symbols,
            timeframe=timeframe,
            lookback=lookback_bars,
        )

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_correlation_matrix",
                "symbols": symbols,
                "warnings": len(result.get("warnings", [])),
            },
        )

        return GetCorrelationMatrixOutput(
            symbols=result["symbols"],
            matrix=result["matrix"],
            warnings=result.get("warnings", []),
            computed_at=result["computed_at"],
            lookback_bars=lookback_bars,
        )

    async def get_drawdown_analysis(
        self,
        lookback_days: int = 30,
    ) -> GetDrawdownAnalysisOutput:
        """Analyze historical and current drawdown metrics."""
        from datetime import timedelta

        now = datetime.now(UTC)
        date_from = (now - timedelta(days=lookback_days)).isoformat()
        date_to = now.isoformat()

        deals = await self.bridge.history_deals_get(date_from, date_to)

        if not deals:
            return GetDrawdownAnalysisOutput(
                current_drawdown_pct=0.0,
                max_drawdown_pct=0.0,
                max_drawdown_date=None,
                avg_daily_drawdown_pct=0.0,
                recovery_factor=0.0,
                circuit_breaker_distance_pct=100.0,
            )

        equity_curve = []
        running_equity = 10000.0

        for deal in sorted(deals, key=lambda d: d.get("time", 0)):
            profit = deal.get("profit", 0)
            running_equity += profit
            equity_curve.append(running_equity)

        if not equity_curve:
            return GetDrawdownAnalysisOutput(
                current_drawdown_pct=0.0,
                max_drawdown_pct=0.0,
                max_drawdown_date=None,
                avg_daily_drawdown_pct=0.0,
                recovery_factor=0.0,
                circuit_breaker_distance_pct=100.0,
            )

        peak = equity_curve[0]
        max_drawdown = 0.0
        max_dd_date = None
        dd_pct_values = []

        for i, equity in enumerate(equity_curve):
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak * 100 if peak > 0 else 0
            dd_pct_values.append(drawdown)

            if drawdown > max_drawdown:
                max_drawdown = drawdown
                if i < len(deals):
                    max_dd_date = datetime.fromtimestamp(
                        deals[i].get("time", 0), tz=UTC
                    ).isoformat()

        current_equity = equity_curve[-1]
        current_peak = max(equity_curve)
        current_dd = (current_peak - current_equity) / current_peak * 100 if current_peak > 0 else 0

        avg_dd = sum(dd_pct_values) / len(dd_pct_values) if dd_pct_values else 0
        recovery = current_equity / max(equity_curve[0], 1) if equity_curve else 0

        initial_balance = 10000.0
        circuit_distance = (
            ((initial_balance * 0.97) / current_equity * 100) - 100 if current_equity > 0 else 100
        )

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_drawdown_analysis",
                "lookback_days": lookback_days,
                "current_dd_pct": round(current_dd, 2),
            },
        )

        return GetDrawdownAnalysisOutput(
            current_drawdown_pct=round(current_dd, 2),
            max_drawdown_pct=round(max_drawdown, 2),
            max_drawdown_date=max_dd_date,
            avg_daily_drawdown_pct=round(avg_dd, 2),
            recovery_factor=round(recovery, 2),
            circuit_breaker_distance_pct=round(circuit_distance, 2),
        )

    async def get_strategy_context(self) -> StrategyContextOutput:
        """Get current strategy context memo."""
        ctx = self.strategy_context.get()

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_strategy_context",
            },
        )

        return StrategyContextOutput(
            context=ctx.get("context", ""),
            last_updated=ctx.get("last_updated"),
            set_by=ctx.get("set_by"),
        )

    async def set_strategy_context(
        self,
        context: str,
        agent_id: str = "unknown",
    ) -> StrategyContextOutput:
        """Set strategy context memo (persisted to disk)."""
        self.strategy_context.set(context, agent_id)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "set_strategy_context",
                "context_length": len(context),
                "agent_id": agent_id,
            },
        )

        return StrategyContextOutput(
            context=context[:2000],
            last_updated=datetime.now(UTC).isoformat(),
            set_by=agent_id,
        )

    async def get_agent_memory(self, key: str) -> AgentMemoryOutput:
        """Get named memory value."""
        result = self.agent_memory.get(key)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "get_agent_memory",
                "key": key,
                "found": result["value"] is not None,
            },
        )

        return AgentMemoryOutput(
            key=key,
            value=result.get("value"),
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
            saved=result["value"] is not None,
        )

    async def set_agent_memory(
        self,
        key: str,
        value: Any,
    ) -> AgentMemoryOutput:
        """Store named memory value (persisted to disk)."""
        self.agent_memory.set(key, value)

        self.audit.log(
            AuditEventType.TOOL_INVOCATION,
            {
                "tool": "set_agent_memory",
                "key": key,
                "value_type": type(value).__name__,
            },
        )

        result = self.agent_memory.get(key)

        return AgentMemoryOutput(
            key=key,
            value=value,
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
            saved=True,
        )


async def handle_get_market_regime(
    service: IntelligenceService,
    args: dict,
) -> dict[str, Any]:
    inp = GetMarketRegimeInput.model_validate(args)
    result = await service.get_market_regime(
        symbol=inp.symbol,
        timeframe=inp.timeframe,
        lookback_bars=inp.lookback_bars,
    )
    return result.model_dump()


async def handle_get_correlation_matrix(
    service: IntelligenceService,
    args: dict,
) -> dict[str, Any]:
    inp = GetCorrelationMatrixInput.model_validate(args)
    result = await service.get_correlation_matrix(
        symbols=inp.symbols,
        timeframe=inp.timeframe,
        lookback_bars=inp.lookback_bars,
    )
    return result.model_dump()


async def handle_get_strategy_context(
    service: IntelligenceService,
    args: dict,
) -> dict[str, Any]:
    result = await service.get_strategy_context()
    return result.model_dump()


async def handle_set_strategy_context(
    service: IntelligenceService,
    args: dict,
) -> dict[str, Any]:
    inp = StrategyContextInput.model_validate(args)
    result = await service.set_strategy_context(context=inp.context)
    return result.model_dump()


async def handle_get_agent_memory(
    service: IntelligenceService,
    args: dict,
) -> dict[str, Any]:
    key = args.get("key", "")
    result = await service.get_agent_memory(key=key)
    return result.model_dump()


async def handle_set_agent_memory(
    service: IntelligenceService,
    args: dict,
) -> dict[str, Any]:
    key = args.get("key", "")
    value = args.get("value", "")
    result = await service.set_agent_memory(key=key, value=value)
    return result.model_dump()


async def handle_get_drawdown_analysis(
    service: IntelligenceService,
    args: dict,
) -> dict[str, Any]:
    inp = GetDrawdownAnalysisInput.model_validate(args)
    result = await service.get_drawdown_analysis(
        lookback_days=inp.lookback_days,
    )
    return result.model_dump()
