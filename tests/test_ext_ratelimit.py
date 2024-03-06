import asyncio
from datetime import datetime, timedelta

import pytest

from src.ext.ratelimit import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_token_bucket_ratelimit():
    token_per_sec = 4
    interval = timedelta(seconds=1 / token_per_sec)
    rate_limit = await TokenBucketRateLimiter.create(1, token_per_sec)
    ticks: list[datetime] = []
    for _ in range(10):
        await rate_limit.acquire()
        ticks.append(datetime.now())
    for i in range(1, len(ticks)):
        assert ticks[i] - ticks[i - 1] >= interval
    del rate_limit


@pytest.mark.asyncio
async def test_token_bucket_order():

    async def acquire(bucket: TokenBucketRateLimiter, wait: float):
        await asyncio.sleep(wait)
        await bucket.acquire()
        return datetime.now()

    every_k_sec = 2
    rate_limit = await TokenBucketRateLimiter.create(1, 1 / every_k_sec)
    ticks = await asyncio.gather(
        acquire(rate_limit, 0),
        acquire(rate_limit, 0.25),
        acquire(rate_limit, 0.5),
        acquire(rate_limit, 0.75),
    )
    for i in range(1, len(ticks)):
        assert ticks[i] > ticks[i - 1]
    del rate_limit
