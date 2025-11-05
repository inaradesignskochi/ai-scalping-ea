"""
Rate limiter utility for API calls and data sources
"""

import asyncio
import time
from collections import deque
from typing import Deque, Tuple


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, rate_per_second: float):
        self.rate = rate_per_second
        self.tokens = rate_per_second
        self.last_update = time.time()
        self.max_tokens = rate_per_second * 2  # Allow burst up to 2x rate

    async def acquire(self) -> bool:
        """Acquire a token. Returns True if allowed, False if rate limited."""
        now = time.time()
        elapsed = now - self.last_update

        # Add tokens based on elapsed time
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
        self.last_update = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True

        return False

    def get_wait_time(self) -> float:
        """Get time to wait for next token"""
        if self.tokens >= 1.0:
            return 0.0

        tokens_needed = 1.0 - self.tokens
        return tokens_needed / self.rate


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for more precise control"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Deque[float] = deque()

    async def acquire(self) -> bool:
        """Check if request is allowed"""
        now = time.time()

        # Remove old requests outside the window
        while self.requests and now - self.requests[0] > self.window_seconds:
            self.requests.popleft()

        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True

        return False

    def get_wait_time(self) -> float:
        """Get time to wait for next request"""
        if len(self.requests) < self.max_requests:
            return 0.0

        oldest_request = self.requests[0]
        return self.window_seconds - (time.time() - oldest_request)


class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts based on API responses"""

    def __init__(self, initial_rate: float, min_rate: float = 0.1, max_rate: float = 100.0):
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.success_count = 0
        self.failure_count = 0
        self.adjustment_factor = 0.1

    async def acquire(self) -> bool:
        """Acquire with adaptive rate limiting"""
        # Simple token bucket with adaptive rate
        limiter = RateLimiter(self.current_rate)
        return await limiter.acquire()

    def record_success(self):
        """Record successful API call"""
        self.success_count += 1
        if self.success_count >= 10:  # Increase rate after 10 successes
            self.current_rate = min(self.max_rate, self.current_rate * (1 + self.adjustment_factor))
            self.success_count = 0

    def record_failure(self):
        """Record failed API call (rate limit or error)"""
        self.failure_count += 1
        if self.failure_count >= 3:  # Decrease rate after 3 failures
            self.current_rate = max(self.min_rate, self.current_rate * (1 - self.adjustment_factor))
            self.failure_count = 0

    def get_current_rate(self) -> float:
        """Get current rate limit"""
        return self.current_rate