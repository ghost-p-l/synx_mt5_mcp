"""Correlation tracker - Cross-symbol correlation matrix calculation."""

import time

import numpy as np
import structlog

log = structlog.get_logger(__name__)


class CorrelationTracker:
    """Calculates and caches Pearson correlation matrix across symbols."""

    def __init__(self, bridge, cache_ttl_seconds: int = 300):
        self._bridge = bridge
        self._ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[float, dict]] = {}

    def _make_cache_key(self, symbols: list[str], timeframe: str, lookback: int) -> str:
        """Create cache key."""
        return f"{','.join(sorted(symbols))}:{timeframe}:{lookback}"

    async def get_matrix(
        self, symbols: list[str], timeframe: str = "H1", lookback: int = 200
    ) -> dict:
        """Get correlation matrix for symbols."""
        cache_key = self._make_cache_key(symbols, timeframe, lookback)
        now = time.time()

        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if now - cached_time < self._ttl:
                return cached_data

        closes = {}
        for sym in symbols:
            rates = await self._bridge.copy_rates_from_pos(sym, timeframe, 0, lookback)
            if rates:
                closes[sym] = np.array([r["close"] for r in rates])

        n = len(symbols)
        valid_syms = [s for s in symbols if s in closes]
        matrix = np.eye(n)

        for i, sym_i in enumerate(valid_syms):
            for j, sym_j in enumerate(valid_syms):
                if i != j:
                    min_len = min(len(closes[sym_i]), len(closes[sym_j]))
                    if min_len > 10:
                        corr = np.corrcoef(closes[sym_i][-min_len:], closes[sym_j][-min_len:])[0, 1]
                        matrix[i, j] = round(float(corr), 3)

        warnings = []
        threshold = 0.75
        for i in range(len(valid_syms)):
            for j in range(i + 1, len(valid_syms)):
                c = matrix[i, j]
                if abs(c) >= threshold:
                    direction = "positively" if c > 0 else "negatively"
                    warnings.append(
                        f"{valid_syms[i]} and {valid_syms[j]} are {direction} "
                        f"correlated ({c:.2f}). High correlation increases exposure risk."
                    )

        result = {
            "symbols": valid_syms,
            "matrix": matrix.tolist(),
            "warnings": warnings,
            "computed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        self._cache[cache_key] = (now, result)
        return result
