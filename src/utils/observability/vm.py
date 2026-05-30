import os
from typing import Any

import aiohttp
from nonebot import get_driver

from ..log import logger_wrapper

logger = logger_wrapper(__name__)

_BASE_URL: str | None = os.getenv("VM_BASE_URL")
_QUERY_TIMEOUT = aiohttp.ClientTimeout(total=5)


class VMClient:
    _client: aiohttp.ClientSession | None = None

    @classmethod
    def is_configured(cls) -> bool:
        return _BASE_URL is not None

    @classmethod
    async def _session(cls) -> aiohttp.ClientSession:
        if cls._client is None:
            cls._client = aiohttp.ClientSession(timeout=_QUERY_TIMEOUT)
        return cls._client

    @classmethod
    async def query(cls, promql: str) -> list[dict[str, Any]]:
        session = await cls._session()
        params = {"query": promql}
        async with session.get(
            f"{_BASE_URL}/api/v1/query", params=params
        ) as resp:
            resp.raise_for_status()
            body = await resp.json()
            return body["data"]["result"]

    @classmethod
    async def query_value(cls, promql: str) -> float | None:
        if _BASE_URL is None:
            return None
        try:
            results = await cls.query(promql)
            if results:
                return float(results[0]["value"][1])
        except Exception as e:
            logger.warning("VMClient query failed", exception=e)
        return None

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            cls._client = None


driver = get_driver()


@driver.on_shutdown
async def _():
    await VMClient.close()
