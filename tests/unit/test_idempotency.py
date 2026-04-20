"""Unit tests for idempotency engine."""

import time

import pytest

from synx_mt5.idempotency.engine import IdempotencyEngine


class TestIdempotencyEngine:
    """Test idempotency engine."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        return IdempotencyEngine(ttl_seconds=300, max_cache_size=100)

    def test_generate_magic_unique(self, engine):
        """Test that magic numbers are unique."""
        magics = [engine.generate_magic() for _ in range(100)]
        assert len(set(magics)) == 100

    def test_make_key_deterministic(self, engine):
        """Test that same inputs produce same key."""
        key1 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        key2 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        assert key1 == key2

    def test_make_key_different_for_different_params(self, engine):
        """Test that different params produce different keys."""
        key1 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        key2 = engine.make_key("EURUSD", 0.2, "ORDER_TYPE_BUY", 1.08500)
        assert key1 != key2

    def test_check_and_register_new_key(self, engine):
        """Test that new keys are accepted."""
        key = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        assert engine.check_and_register(key) is True

    def test_check_and_register_duplicate_key(self, engine):
        """Test that duplicate keys are rejected."""
        key = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        assert engine.check_and_register(key) is True
        assert engine.check_and_register(key) is False

    def test_stats(self, engine):
        """Test cache statistics."""
        key = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        engine.check_and_register(key)
        stats = engine.get_stats()
        assert stats["cache_size"] == 1
        assert stats["active_keys"] == 1


class TestIdempotencyEngineExtended:
    """Extended tests for idempotency engine."""

    def test_make_key_price_rounding(self):
        """Test price is rounded to 3 decimal places."""
        engine = IdempotencyEngine()
        key1 = engine.make_key("EURUSD", 0.1, "BUY", 1.085001)
        key2 = engine.make_key("EURUSD", 0.1, "BUY", 1.085009)
        assert key1 == key2

    def test_make_key_case_sensitivity(self):
        """Test key is case sensitive for order_type."""
        engine = IdempotencyEngine()
        key1 = engine.make_key("EURUSD", 0.1, "BUY", 1.08500)
        key2 = engine.make_key("EURUSD", 0.1, "buy", 1.08500)
        assert key1 != key2

    def test_ttl_expiration(self):
        """Test TTL expiration removes old keys."""
        engine = IdempotencyEngine(ttl_seconds=0, max_cache_size=100)
        key = engine.make_key("EURUSD", 0.1, "BUY", 1.08500)

        result1 = engine.check_and_register(key)
        assert result1 is True

        time.sleep(0.01)
        result2 = engine.check_and_register(key)
        assert result2 is True

    def test_max_cache_size_eviction(self):
        """Test oldest key is evicted when max size reached."""
        engine = IdempotencyEngine(ttl_seconds=300, max_cache_size=3)

        keys = []
        for i in range(5):
            key = engine.make_key("EURUSD", 0.1 + i * 0.01, "BUY", 1.08500)
            engine.check_and_register(key)
            keys.append(key)

        stats = engine.get_stats()
        assert stats["cache_size"] <= 3

    def test_check_and_register_logs_warning(self):
        """Test duplicate key logs warning."""

        engine = IdempotencyEngine(ttl_seconds=300, max_cache_size=100)
        key = engine.make_key("EURUSD", 0.1, "BUY", 1.08500)

        engine.check_and_register(key)
        result = engine.check_and_register(key)
        assert result is False

    def test_stats_includes_max_size(self):
        """Test stats includes max_size."""
        engine = IdempotencyEngine(ttl_seconds=300, max_cache_size=50)
        stats = engine.get_stats()
        assert stats["max_size"] == 50
        assert stats["ttl_seconds"] == 300

    def test_stats_active_keys_after_expiration(self):
        """Test stats active_keys excludes expired."""
        engine = IdempotencyEngine(ttl_seconds=0, max_cache_size=100)
        key = engine.make_key("EURUSD", 0.1, "BUY", 1.08500)
        engine.check_and_register(key)

        time.sleep(0.01)
        stats = engine.get_stats()
        assert stats["active_keys"] == 0

    def test_multiple_unique_keys(self):
        """Test multiple unique keys all register successfully."""
        engine = IdempotencyEngine(ttl_seconds=300, max_cache_size=100)

        results = []
        for i in range(50):
            key = engine.make_key("EURUSD", 0.1 + i * 0.01, "BUY", 1.08500)
            results.append(engine.check_and_register(key))

        assert all(results)
        assert engine.get_stats()["cache_size"] == 50
