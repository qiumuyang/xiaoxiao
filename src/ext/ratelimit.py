import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum


class RateLimiter(ABC):

    def __init__(self) -> None:
        self._wait_queue = asyncio.Queue()

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}"
                f"(waiting={self._wait_queue.qsize()})")

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


class TokenBucketRateLimiter(RateLimiter):

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


class RateLimitManager:

    rate_limiters: dict[str, RateLimiter] = {}

    @classmethod
    def create_or_get(cls, key: str, rate_limit: type[RateLimiter], *args,
                      **kwargs) -> RateLimiter:
        if key not in cls.rate_limiters:
            cls.rate_limiters[key] = rate_limit(*args, **kwargs)
        return cls.rate_limiters[key]


class RateLimitType(Enum):
    """Rate limit type.

    GROUP: 每个群内的所有用户使用同一个速率限制。
    USER: 每个用户（无论在何处）使用同一个速率限制。
    SESSION: 每个用户在不同群内使用独立的速率限制。
    """
    GROUP = "group"
    USER = "user"
    SESSION = "session"
