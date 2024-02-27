import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum

from typing_extensions import Self


class RateLimiter(ABC):

    def __init__(self, *args, **kwargs) -> None:
        self._wait_queue = asyncio.Queue()

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}"
                f"(waiting={self._wait_queue.qsize()})")

    @classmethod
    async def create(cls, *args, **kwargs):
        """Create a new rate limiter instance."""
        raise NotImplementedError

    @abstractmethod
    def try_acquire(self) -> bool:
        """Acquire from the rate limiter if available."""

    @abstractmethod
    async def acquire(self) -> None:
        """Acquire from the rate limiter, blocking until available."""

    def acquire_sync(self) -> None:
        """Acquire from the rate limiter, blocking until available."""
        while not self.try_acquire():
            pass


class TokenBucketRateLimiter(RateLimiter):

    __slots__ = ("capacity", "tokens", "refill_rate", "last_update")

    @classmethod
    async def create(  # type: ignore
            cls, capacity: int, refill_rate: float) -> Self:
        self = cls()
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_update = datetime.now()
        asyncio.create_task(self.refill_tokens())
        return self

    def try_acquire(self) -> bool:
        if self._wait_queue.empty() and self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

    async def acquire(self) -> None:
        if self.try_acquire():
            return
        future = asyncio.Future()
        self._wait_queue.put_nowait(future)
        await future

    async def refill_tokens(self) -> None:
        """Refill tokens based on the elapsed time since the last update."""
        while True:
            await asyncio.sleep(1 / self.refill_rate)
            now = datetime.now()
            time_elapsed = now - self.last_update
            refill_count = time_elapsed.total_seconds() * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + refill_count)
            self.last_update = now
            # wake up waiting tasks
            while not self._wait_queue.empty() and self.tokens >= 1:
                future = self._wait_queue.get_nowait()
                future.set_result(None)
                self.tokens -= 1


class RateLimitManager:

    rate_limiters: dict[str, RateLimiter] = {}

    @classmethod
    async def create_or_get(cls, key: str, rate_limit: type[RateLimiter],
                            *args, **kwargs) -> RateLimiter:
        if key not in cls.rate_limiters:
            cls.rate_limiters[key] = await rate_limit.create(*args, **kwargs)
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
