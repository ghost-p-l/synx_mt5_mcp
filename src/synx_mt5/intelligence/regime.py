"""Market regime detector - Classifies market conditions using ADX, ATR, EMA."""

import numpy as np
import structlog

log = structlog.get_logger(__name__)


class MarketRegimeDetector:
    """Classifies market into trending/ranging/volatility regimes."""

    REGIMES = {
        "TRENDING_UP": "Strong uptrend — ADX above threshold, price above 200MA",
        "TRENDING_DOWN": "Strong downtrend — ADX above threshold, price below 200MA",
        "RANGING": "Low-trend ranging market — ADX below threshold",
        "HIGH_VOLATILITY": "Elevated volatility — ATR expansion detected",
        "LOW_VOLATILITY": "Compressed volatility — potential breakout setup",
        "UNKNOWN": "Insufficient data for classification",
    }

    def __init__(
        self,
        adx_threshold: float = 25.0,
        volatility_high: float = 0.005,
        volatility_low: float = 0.001,
    ):
        self.adx_threshold = adx_threshold
        self.volatility_high = volatility_high
        self.volatility_low = volatility_low

    def classify(self, rates: list[dict]) -> dict:
        """Classify market regime from OHLCV data."""
        if len(rates) < 50:
            return {
                "regime": "UNKNOWN",
                "confidence": 0.0,
                "reason": "Insufficient data (minimum 50 bars required)",
            }

        closes = np.array([r["close"] for r in rates])
        highs = np.array([r["high"] for r in rates])
        lows = np.array([r["low"] for r in rates])

        adx = self._calc_adx(highs, lows, closes, 14)
        atr = self._calc_atr(highs, lows, closes, 14)
        if len(closes) >= 200:
            ema200 = self._calc_ema(closes, 200)
            ema200_value = ema200[-1]
        else:
            ema200_value = closes.mean()

        current_price = closes[-1]
        atr_norm = atr[-1] / current_price if current_price > 0 else 0

        if atr_norm > self.volatility_high:
            regime = "HIGH_VOLATILITY"
            confidence = min(1.0, (atr_norm - self.volatility_high) / self.volatility_high)
        elif atr_norm < self.volatility_low:
            regime = "LOW_VOLATILITY"
            confidence = min(1.0, 1 - atr_norm / self.volatility_low)
        elif adx[-1] > self.adx_threshold:
            regime = "TRENDING_UP" if current_price > ema200_value else "TRENDING_DOWN"
            confidence = min(1.0, (adx[-1] - self.adx_threshold) / 25)
        else:
            regime = "RANGING"
            confidence = min(1.0, 1 - adx[-1] / self.adx_threshold)

        return {
            "regime": regime,
            "description": self.REGIMES[regime],
            "confidence": round(confidence, 3),
            "adx": round(float(adx[-1]), 2),
            "atr_normalised": round(atr_norm, 6),
            "price_vs_ema200": "above" if current_price > ema200_value else "below",
            "volatility_pct": round(atr_norm * 100, 3),
        }

    @staticmethod
    def _calc_atr(highs, lows, closes, period: int = 14) -> np.ndarray:
        """Calculate Average True Range."""
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(abs(highs[1:] - closes[:-1]), abs(lows[1:] - closes[:-1])),
        )
        return np.convolve(tr, np.ones(period) / period, mode="valid")

    @staticmethod
    def _calc_ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average."""
        k = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[period - 1] = data[:period].mean()
        for i in range(period, len(data)):
            ema[i] = data[i] * k + ema[i - 1] * (1 - k)
        return ema

    @staticmethod
    def _calc_adx(highs, lows, closes, period: int = 14) -> np.ndarray:
        """Calculate Average Directional Index."""
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(abs(highs[1:] - closes[:-1]), abs(lows[1:] - closes[:-1])),
        )
        atr14 = np.convolve(tr, np.ones(period) / period, mode="valid")
        plus14 = np.convolve(plus_dm, np.ones(period) / period, mode="valid")
        minus14 = np.convolve(minus_dm, np.ones(period) / period, mode="valid")
        plus_di = 100 * plus14 / (atr14 + 1e-9)
        minus_di = 100 * minus14 / (atr14 + 1e-9)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
        return np.convolve(dx, np.ones(period) / period, mode="valid")
