import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TypeVar

T = TypeVar("T")


class RateLimit(ABC):

    def __init__(self) -> None:
        self._wait_queue = asyncio.Queue()

    @abstractmethod
    def try_acquire(self) -> bool:
        """Acquire from the rate limiter if available."""

    async def acquire(self) -> None:
        """Acquire from the rate limiter, blocking until available."""
        while not self.try_acquire():
            await asyncio.sleep(0)  # yield to other tasks

    def acquire_sync(self) -> None:
        """Acquire from the rate limiter, blocking until available."""
        while not self.try_acquire():
            pass


class TokenBucketRateLimit(RateLimit):

    __slots__ = ("capacity", "tokens", "refill_rate", "last_update")

    def __init__(self, capacity: int, refill_rate: float) -> None:
        super().__init__()
        self.capacity = capacity
        self.tokens = capacity  # fill the bucket at the beginning
        self.refill_rate = refill_rate  # tokens per second
        self.last_update = datetime.now()

    def try_acquire(self) -> bool:
        self._update_tokens()
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

    def _update_tokens(self) -> None:
        """ Refill tokens based on the elapsed time since the last update. """
        now = datetime.now()
        time_elapsed = now - self.last_update
        refill_count = time_elapsed.total_seconds() * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_count)
        self.last_update = now
