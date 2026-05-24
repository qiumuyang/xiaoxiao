import asyncio
from typing import cast

from fastapi import Response
from nonebot import get_driver
from nonebot.drivers.fastapi import Driver as FastAPIDriver

from ..persistence import Mongo
from .metrics import MONGODB_UP, get_metrics_text

driver = cast(FastAPIDriver, get_driver())


@driver.on_startup
async def register_metrics_routes():
    app = driver.server_app

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        await _check_mongo()
        return Response(content=get_metrics_text(), media_type="text/plain")

    @app.get("/health", include_in_schema=False)
    async def health():
        return Response(status_code=200)


async def _check_mongo():
    try:
        await asyncio.wait_for(
            Mongo._client.admin.command("ping"),
            timeout=0.5,
        )
        MONGODB_UP.set(1)
    except Exception:
        MONGODB_UP.set(0)
