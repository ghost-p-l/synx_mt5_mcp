"""Rate limiter for tool access control."""

import time
from collections import deque

import structlog

log = structlog.get_logger(__name__)


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens: float = float(capacity)
        self.last_update = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class SlidingWindowCounter:
    """Sliding window rate limiter."""

    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.requests: deque = deque()

    def is_allowed(self) -> bool:
        """Check if request is allowed."""
        now = time.time()
        cutoff = now - self.window_seconds

        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()

        if len(self.requests) < self.max_calls:
            self.requests.append(now)
            return True
        return False


class RateLimiter:
    """Per-tool rate limiter."""

    def __init__(self, limits: dict):
        self._limits: dict[str, SlidingWindowCounter] = {}
        for tool_name, config in limits.items():
            if isinstance(config, dict):
                calls = config.get("calls", 60)
                window = config.get("window_seconds", 60)
                self._limits[tool_name] = SlidingWindowCounter(calls, window)

    def check(self, tool_name: str) -> bool:
        """Check if tool call is allowed."""
        if tool_name not in self._limits:
            return True

        allowed = self._limits[tool_name].is_allowed()
        if not allowed:
            log.warning("rate_limit_exceeded", tool=tool_name)
        return allowed

    def update_limits(self, limits: dict) -> None:
        """Update rate limits at runtime."""
        self._limits.clear()
        for tool_name, config in limits.items():
            if isinstance(config, dict):
                calls = config.get("calls", 60)
                window = config.get("window_seconds", 60)
                self._limits[tool_name] = SlidingWindowCounter(calls, window)
