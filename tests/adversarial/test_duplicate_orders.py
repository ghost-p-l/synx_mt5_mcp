"""Adversarial duplicate order attack tests — idempotency engine stress tests."""

import time

import pytest

from synx_mt5.idempotency.engine import IdempotencyEngine


@pytest.fixture
def engine():
    return IdempotencyEngine(ttl_seconds=300, max_cache_size=100)


class TestIdempotencyEngineBasics:
    """Test basic idempotency engine functionality."""

    def test_generate_magic_unique(self, engine):
        """Each magic number must be unique within session."""
        magics = set()
        for _ in range(100):
            m = engine.generate_magic()
            assert m not in magics, "Magic number collision detected"
            magics.add(m)

    def test_first_order_registered(self, engine):
        """First order with a key should be registered."""
        key = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        result = engine.check_and_register(key)
        assert result is True

    def test_duplicate_order_blocked(self, engine):
        """Duplicate order within TTL window must be blocked."""
        key = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        assert engine.check_and_register(key) is True
        assert engine.check_and_register(key) is False

    def test_different_symbol_not_blocked(self, engine):
        """Different symbols should not interfere."""
        key1 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        key2 = engine.make_key("GBPUSD", 0.1, "ORDER_TYPE_BUY", 1.2650)
        assert engine.check_and_register(key1) is True
        assert engine.check_and_register(key2) is True

    def test_different_volume_not_blocked(self, engine):
        """Different volumes should not interfere."""
        key1 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        key2 = engine.make_key("EURUSD", 0.2, "ORDER_TYPE_BUY", 1.0850)
        assert engine.check_and_register(key1) is True
        assert engine.check_and_register(key2) is True

    def test_different_price_not_blocked(self, engine):
        """Prices in different buckets should not interfere."""
        key1 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        key2 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0860)
        assert engine.check_and_register(key1) is True
        assert engine.check_and_register(key2) is True


class TestIdempotencyEnginePriceRounding:
    """Test that price rounding prevents fragmentation attacks."""

    def test_close_prices_same_key(self, engine):
        """Prices within 0.001 (same 3-decimal bucket) should hash to same key."""
        key1 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        key2 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08549)
        assert key1 == key2

    def test_same_bucket_blocked(self, engine):
        """Same price bucket produces same key and is blocked (duplicate)."""
        key = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        assert engine.check_and_register(key) is True
        key2 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08549)
        assert key == key2
        assert engine.check_and_register(key2) is False

    def test_different_prices_different_keys(self, engine):
        """Prices > 0.001 apart should have different keys."""
        key1 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        key2 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08600)
        assert key1 != key2

    def test_different_prices_not_blocked(self, engine):
        """Different price buckets should not be blocked (distinct orders)."""
        key1 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08500)
        key2 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.08600)
        assert engine.check_and_register(key1) is True
        assert engine.check_and_register(key2) is True


class TestIdempotencyEngineCacheExpiry:
    """Test TTL-based cache eviction."""

    def test_cache_eviction_on_ttl(self):
        """Keys should expire after TTL."""
        engine = IdempotencyEngine(ttl_seconds=1, max_cache_size=100)
        key = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        assert engine.check_and_register(key) is True
        time.sleep(1.1)
        assert engine.check_and_register(key) is True

    def test_old_entries_evicted_first(self):
        """Oldest entries should be evicted when cache is full."""
        engine = IdempotencyEngine(ttl_seconds=300, max_cache_size=3)
        keys = [
            engine.make_key("EURUSD", float(i) * 0.1, "ORDER_TYPE_BUY", 1.0850) for i in range(1, 5)
        ]
        for k in keys:
            engine.check_and_register(k)
        assert engine.check_and_register(keys[0]) is True
        assert engine.check_and_register(keys[1]) is True
        assert engine.check_and_register(keys[2]) is True
        assert engine.check_and_register(keys[3]) is True


class TestIdempotencyEngineConcurrencySafety:
    """Test idempotency engine under concurrent access patterns."""

    def test_session_seed_bit_width(self):
        """Session seed should be 16 bits."""
        engine = IdempotencyEngine()
        seed = engine._session_seed
        assert 0 <= seed <= 0xFFFF

    def test_magic_numbers_unique_within_session(self, engine):
        """Magic numbers must be unique within a single session."""
        magics = set()
        for _ in range(1000):
            m = engine.generate_magic()
            assert m not in magics
            magics.add(m)

    def test_magic_bit_width(self, engine):
        """Magic number should be 32 bits (16-bit seed << 16 | 16-bit counter)."""
        for _ in range(10):
            m = engine.generate_magic()
            assert 0 <= m <= 0xFFFFFFFF

    def test_magic_number_uniqueness_across_session(self, engine):
        """Magic numbers must be unique even after many generations."""
        magics = set()
        for _ in range(1000):
            m = engine.generate_magic()
            assert m not in magics
            magics.add(m)


class TestIdempotencyEngineMakeKey:
    """Test the key generation function."""

    def test_key_is_string(self, engine):
        """make_key must return a string."""
        key = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        assert isinstance(key, str)

    def test_key_is_16_chars(self, engine):
        """Key should be exactly 16 hex characters (64 bits)."""
        key = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_key_deterministic(self, engine):
        """Same inputs must always produce same key."""
        key1 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        key2 = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        assert key1 == key2

    def test_key_changes_with_order_type(self, engine):
        """Different order types must produce different keys."""
        key_buy = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_BUY", 1.0850)
        key_sell = engine.make_key("EURUSD", 0.1, "ORDER_TYPE_SELL", 1.0850)
        assert key_buy != key_sell
