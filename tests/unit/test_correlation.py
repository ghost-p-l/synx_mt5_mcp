"""Unit tests for correlation module."""

from unittest.mock import MagicMock

import pytest

from synx_mt5.intelligence.correlation import CorrelationTracker


class TestCorrelationTracker:
    """Test CorrelationTracker class."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = MagicMock()
        return bridge

    @pytest.fixture
    def tracker(self, mock_bridge):
        """Create correlation tracker."""
        return CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=60)

    def test_init_default_ttl(self, mock_bridge):
        """Test init with default TTL."""
        tracker = CorrelationTracker(bridge=mock_bridge)
        assert tracker._ttl == 300

    def test_init_custom_ttl(self, mock_bridge):
        """Test init with custom TTL."""
        tracker = CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=120)
        assert tracker._ttl == 120

    def test_make_cache_key(self, tracker):
        """Test cache key generation."""
        key = tracker._make_cache_key(["EURUSD", "GBPUSD"], "H1", 200)
        assert "EURUSD" in key
        assert "GBPUSD" in key
        assert "H1" in key
        assert "200" in key

    def test_make_cache_key_order_independent(self, tracker):
        """Test cache key is same regardless of symbol order."""
        key1 = tracker._make_cache_key(["EURUSD", "GBPUSD"], "H1", 200)
        key2 = tracker._make_cache_key(["GBPUSD", "EURUSD"], "H1", 200)
        assert key1 == key2


class TestCorrelationTrackerGetMatrix:
    """Test get_matrix method."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = MagicMock()
        return bridge

    @pytest.mark.asyncio
    async def test_get_matrix_empty_symbols(self, mock_bridge):
        """Test get_matrix with empty symbols list."""
        tracker = CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=60)
        result = await tracker.get_matrix([])
        assert result["symbols"] == []
        assert result["matrix"] == []

    @pytest.mark.asyncio
    async def test_get_matrix_with_mocked_data(self, mock_bridge):
        """Test get_matrix with mocked data."""
        rates_eurusd = [{"close": 1.08 + i * 0.001} for i in range(200)]
        rates_gbpusd = [{"close": 1.26 + i * 0.001} for i in range(200)]

        async def mock_copy_rates(symbol, tf, pos, count):
            if symbol == "EURUSD":
                return rates_eurusd
            elif symbol == "GBPUSD":
                return rates_gbpusd
            return []

        mock_bridge.copy_rates_from_pos = mock_copy_rates

        tracker = CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=60)
        result = await tracker.get_matrix(["EURUSD", "GBPUSD"], "H1", 200)

        assert len(result["symbols"]) == 2
        assert "EURUSD" in result["symbols"]
        assert "GBPUSD" in result["symbols"]
        assert len(result["matrix"]) == 2

    @pytest.mark.asyncio
    async def test_get_matrix_caches_result(self, mock_bridge):
        """Test get_matrix caches results."""
        mock_call_count = 0

        async def mock_copy_rates(symbol, tf, pos, count):
            nonlocal mock_call_count
            mock_call_count += 1
            return [{"close": 1.08 + i * 0.001} for i in range(200)]

        mock_bridge.copy_rates_from_pos = mock_copy_rates

        tracker = CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=60)

        await tracker.get_matrix(["EURUSD"], "H1", 200)
        await tracker.get_matrix(["EURUSD"], "H1", 200)
        await tracker.get_matrix(["EURUSD"], "H1", 200)

        assert mock_call_count == 1

    @pytest.mark.asyncio
    async def test_cache_expiry(self, mock_bridge):
        """Test cache expires after TTL."""
        mock_call_count = 0

        async def mock_copy_rates(symbol, tf, pos, count):
            nonlocal mock_call_count
            mock_call_count += 1
            return [{"close": 1.08 + i * 0.001} for i in range(200)]

        mock_bridge.copy_rates_from_pos = mock_copy_rates

        tracker = CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=0)

        await tracker.get_matrix(["EURUSD"], "H1", 200)
        import time

        time.sleep(0.1)
        await tracker.get_matrix(["EURUSD"], "H1", 200)

        assert mock_call_count == 2

    @pytest.mark.asyncio
    async def test_get_matrix_single_symbol(self, mock_bridge):
        """Test get_matrix with single symbol."""
        rates = [{"close": 1.08 + i * 0.001} for i in range(200)]

        async def mock_copy_rates(symbol, tf, pos, count):
            return rates

        mock_bridge.copy_rates_from_pos = mock_copy_rates

        tracker = CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=60)
        result = await tracker.get_matrix(["EURUSD"], "H1", 200)

        assert len(result["symbols"]) == 1
        assert result["matrix"][0][0] == 1.0

    @pytest.mark.asyncio
    async def test_get_matrix_returns_warnings(self, mock_bridge):
        """Test get_matrix returns correlation warnings."""
        rates = [{"close": 1.0 + i * 0.001} for i in range(200)]

        async def mock_copy_rates(symbol, tf, pos, count):
            return rates

        mock_bridge.copy_rates_from_pos = mock_copy_rates

        tracker = CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=60)
        result = await tracker.get_matrix(["EURUSD", "GBPUSD"], "H1", 200)

        assert "warnings" in result

    @pytest.mark.asyncio
    async def test_get_matrix_includes_computed_at(self, mock_bridge):
        """Test get_matrix includes computed_at timestamp."""
        rates = [{"close": 1.08 + i * 0.001} for i in range(200)]

        async def mock_copy_rates(symbol, tf, pos, count):
            return rates

        mock_bridge.copy_rates_from_pos = mock_copy_rates

        tracker = CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=60)
        result = await tracker.get_matrix(["EURUSD"], "H1", 200)

        assert "computed_at" in result

    @pytest.mark.asyncio
    async def test_get_matrix_different_timeframes(self, mock_bridge):
        """Test get_matrix with different timeframes."""
        rates = [{"close": 1.08 + i * 0.001} for i in range(200)]

        async def mock_copy_rates(symbol, tf, pos, count):
            return rates

        mock_bridge.copy_rates_from_pos = mock_copy_rates

        tracker = CorrelationTracker(bridge=mock_bridge, cache_ttl_seconds=60)

        result_m5 = await tracker.get_matrix(["EURUSD"], "M5", 200)
        result_h1 = await tracker.get_matrix(["EURUSD"], "H1", 200)

        assert "computed_at" in result_m5
        assert "computed_at" in result_h1
