from typing import cast

from fastapi import Response
from nonebot import get_driver
from nonebot.drivers.fastapi import Driver as FastAPIDriver

from .metrics import get_metrics_text

driver = cast(FastAPIDriver, get_driver())


@driver.on_startup
async def register_metrics_routes():
    app = driver.server_app

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(content=get_metrics_text(), media_type="text/plain")

    @app.get("/health", include_in_schema=False)
    async def health():
        return Response(status_code=200)
