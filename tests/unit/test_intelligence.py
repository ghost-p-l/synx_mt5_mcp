"""Unit tests for intelligence layer."""

import pytest

from synx_mt5.intelligence.mql5_codegen import MQL5CodeGenerator
from synx_mt5.intelligence.regime import MarketRegimeDetector


class TestMarketRegimeDetector:
    """Test market regime detection."""

    @pytest.fixture
    def detector(self):
        return MarketRegimeDetector()

    @pytest.fixture
    def sample_rates(self):
        """Generate sample OHLCV data."""
        import numpy as np

        rates = []
        base_price = 100.0
        for i in range(100):
            close = base_price + np.random.randn() * 2
            rates.append(
                {
                    "time": i,
                    "open": close - 0.5,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "tick_volume": 1000,
                    "spread": 2,
                    "real_volume": 1000,
                }
            )
        return rates

    def test_insufficient_data(self, detector):
        """Test that insufficient data returns UNKNOWN."""
        rates = [{"close": 100}] * 10
        result = detector.classify(rates)
        assert result["regime"] == "UNKNOWN"

    def test_classification_returns_valid_regime(self, detector, sample_rates):
        """Test that classification returns valid regime."""
        result = detector.classify(sample_rates)
        assert result["regime"] in [
            "TRENDING_UP",
            "TRENDING_DOWN",
            "RANGING",
            "HIGH_VOLATILITY",
            "LOW_VOLATILITY",
        ]

    def test_regime_output_format(self, detector, sample_rates):
        """Test output contains all expected fields."""
        result = detector.classify(sample_rates)
        assert "regime" in result
        assert "confidence" in result
        assert "description" in result
        assert "adx" in result
        assert "atr_normalised" in result
        assert "volatility_pct" in result

    def test_regime_descriptions(self, detector):
        """Test regime descriptions are defined."""
        assert "TRENDING_UP" in MarketRegimeDetector.REGIMES
        assert "TRENDING_DOWN" in MarketRegimeDetector.REGIMES
        assert "RANGING" in MarketRegimeDetector.REGIMES
        assert "HIGH_VOLATILITY" in MarketRegimeDetector.REGIMES
        assert "LOW_VOLATILITY" in MarketRegimeDetector.REGIMES
        assert "UNKNOWN" in MarketRegimeDetector.REGIMES

    def test_custom_thresholds(self):
        """Test custom threshold configuration."""
        detector = MarketRegimeDetector(
            adx_threshold=30.0, volatility_high=0.01, volatility_low=0.0005
        )
        assert detector.adx_threshold == 30.0
        assert detector.volatility_high == 0.01
        assert detector.volatility_low == 0.0005

    def test_high_volatility_regime(self):
        """Test HIGH_VOLATILITY regime detection."""
        import numpy as np

        detector = MarketRegimeDetector(volatility_high=0.001, volatility_low=0.0001)

        rates = []
        base_price = 100.0
        for i in range(100):
            close = base_price + np.random.randn() * 5
            rates.append(
                {
                    "time": i,
                    "open": close - 0.5,
                    "high": close + 5.0,
                    "low": close - 5.0,
                    "close": close,
                    "tick_volume": 1000,
                    "spread": 2,
                    "real_volume": 1000,
                }
            )

        result = detector.classify(rates)
        assert result["regime"] in ["HIGH_VOLATILITY", "TRENDING_UP", "TRENDING_DOWN"]

    def test_low_volatility_regime(self):
        """Test LOW_VOLATILITY regime detection."""
        detector = MarketRegimeDetector(volatility_high=0.01, volatility_low=0.005)

        rates = []
        for i in range(100):
            rates.append(
                {
                    "time": i,
                    "open": 100.0,
                    "high": 100.1,
                    "low": 99.9,
                    "close": 100.0 + (i % 2) * 0.01,
                    "tick_volume": 100,
                    "spread": 1,
                    "real_volume": 100,
                }
            )

        result = detector.classify(rates)
        assert result["regime"] in ["LOW_VOLATILITY", "RANGING"]

    def test_confidence_range(self, detector, sample_rates):
        """Test confidence is between 0 and 1."""
        result = detector.classify(sample_rates)
        assert 0.0 <= result["confidence"] <= 1.0


class TestMQL5CodeGenerator:
    """Test MQL5 code generation."""

    @pytest.fixture
    def generator(self):
        return MQL5CodeGenerator()

    def test_generate_indicator(self, generator):
        """Test indicator code generation."""
        spec = {
            "name": "TestRSI",
            "type": "indicator",
            "outputs": [{"name": "RSI", "color": "Red"}],
            "parameters": [{"name": "Period", "default": 14}],
        }
        code = generator.generate_from_spec(spec)
        assert "TestRSI.mq5" in code
        assert "indicator_buffers" in code
        assert "OnInit" in code

    def test_generate_ea(self, generator):
        """Test EA code generation."""
        spec = {
            "name": "TestEA",
            "type": "ea",
        }
        code = generator.generate_from_spec(spec)
        assert "TestEA.mq5" in code
        assert "OnInit" in code
        assert "OnTick" in code

    def test_generate_script(self, generator):
        """Test script code generation."""
        spec = {
            "name": "TestScript",
            "type": "script",
        }
        code = generator.generate_from_spec(spec)
        assert "TestScript.mq5" in code
        assert "OnStart" in code
        assert "script_show_inputs" in code

    def test_invalid_type_raises_error(self, generator):
        """Test that invalid type raises ValueError."""
        with pytest.raises(ValueError):
            generator.generate_from_spec({"type": "invalid"})
