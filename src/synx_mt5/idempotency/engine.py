"""Idempotency engine - Prevents duplicate orders from LLM retries."""

import hashlib
import time
from collections import OrderedDict

import structlog

log = structlog.get_logger(__name__)


class IdempotencyEngine:
    """
    Prevents duplicate order execution.
    Uses magic number + TTL dedup cache.
    """

    def __init__(self, ttl_seconds: int = 300, max_cache_size: int = 10000):
        self.ttl = ttl_seconds
        self.max_size = max_cache_size
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._magic_counter = 0
        self._session_seed = int(time.time()) & 0xFFFF

    def generate_magic(self) -> int:
        """Generate unique magic number for this session."""
        self._magic_counter = (self._magic_counter + 1) & 0xFFFF
        return (self._session_seed << 16) | self._magic_counter

    def make_key(self, symbol: str, volume: float, order_type: str, price: float) -> str:
        """Create idempotency key from order parameters."""
        price_rounded = round(price, 3)
        raw = f"{symbol}:{volume}:{order_type}:{price_rounded}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def check_and_register(self, key: str) -> bool:
        """
        Check if key exists, register if not.
        Returns True if new key (should proceed), False if duplicate.
        """
        now = time.time()

        expired = [k for k, ts in self._cache.items() if now - ts > self.ttl]
        for k in expired:
            del self._cache[k]

        if key in self._cache:
            log.warning("duplicate_order_blocked", key=key, age=now - self._cache[key])
            return False

        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        self._cache[key] = now
        return True

    def get_stats(self) -> dict:
        """Get cache statistics."""
        now = time.time()
        active = [k for k, ts in self._cache.items() if now - ts <= self.ttl]
        return {
            "cache_size": len(self._cache),
            "active_keys": len(active),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl,
        }
