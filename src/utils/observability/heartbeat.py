import asyncio
import os
import random

import aiohttp
from nonebot import get_driver

from src.utils.log import logger_wrapper

from .metrics import GATEWAY_HEALTHY

logger = logger_wrapper(__name__)

ONEBOT_URL = os.getenv("ONEBOT_URL", "http://127.0.0.1:3000")
_INTERVAL = 300
_MAX_JITTER = 300


_heartbeat_task: asyncio.Task | None = None


@get_driver().on_startup
async def _start_gateway_heartbeat():
    global _heartbeat_task

    async def _loop():
        while True:
            await asyncio.sleep(_INTERVAL + random.randint(0, _MAX_JITTER))
            try:
                async with (
                    aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as session,
                    session.get(f"{ONEBOT_URL}/get_login_info") as resp,
                ):
                    data = await resp.json()
                    if data.get("retcode") == 0:
                        GATEWAY_HEALTHY.set(1)
                    else:
                        logger.warning(
                            "Gateway unhealthy: retcode=%s", data.get("retcode")
                        )
                        GATEWAY_HEALTHY.set(0)
            except Exception:
                logger.exception("Gateway heartbeat failed")
                GATEWAY_HEALTHY.set(0)

    _heartbeat_task = asyncio.create_task(_loop())
