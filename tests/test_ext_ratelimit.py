from datetime import datetime, timedelta

import pytest

from src.ext.ratelimit import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_token_bucket_ratelimit():
    eps = 1e-4
    token_per_sec = 5
    rate_limit = TokenBucketRateLimiter(1, token_per_sec)
    ticks = []
    for _ in range(10):
        await rate_limit.acquire()
        ticks.append(datetime.now())
    for i in range(1, len(ticks)):
        assert ticks[i] - ticks[i - 1] >= timedelta(seconds=1 / token_per_sec -
                                                    eps)
