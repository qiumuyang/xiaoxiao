"""Alertmanager webhook → OneBot QQ group message."""
import logging
import os

import aiohttp
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alert_bridge")

ONEBOT_URL = os.getenv("ONEBOT_URL", "http://127.0.0.1:3000")
GROUP_ID = int(os.getenv("ALERT_GROUP_ID", "0"))
AT_QQ = int(os.getenv("ALERT_AT_QQ", "0"))

if not GROUP_ID:
    raise RuntimeError("ALERT_GROUP_ID env not set")
if not AT_QQ:
    raise RuntimeError("ALERT_AT_QQ env not set")

SEVERITY_ICON = {"critical": "\U0001f525", "warning": "\u26a0\ufe0f"}


def format_alert(alert: dict) -> str:
    icon = SEVERITY_ICON.get(alert["labels"].get("severity", ""), "")
    name = alert["labels"]["alertname"]
    status = alert["status"]
    summary = alert["annotations"].get("summary", name)
    desc = alert["annotations"].get("description", "")

    parts = [f"[CQ:at,qq={AT_QQ}]", ""]
    if status == "resolved":
        parts.append("[鸮鸮 恢复]")
        parts.append(f"\u2705 [已恢复] {summary}")
    else:
        parts.append("[鸮鸮 告警]")
        parts.append(f"{icon} {summary}")
        if desc:
            parts.append(f"   {desc}")
    return "\n".join(parts)


async def handle_alert(request: web.Request) -> web.Response:
    body = await request.json()
    logger.info("Received alert hook: %d alerts", len(body.get("alerts", [])))
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10)
    ) as session:
        for alert in body.get("alerts", []):
            if alert["status"] not in ("firing", "resolved"):
                continue
            message = format_alert(alert)
            try:
                resp = await session.post(
                    f"{ONEBOT_URL}/send_group_msg",
                    json={"group_id": GROUP_ID, "message": message},
                )
                result = await resp.text()
                logger.info("QQ send result: %s", result)
            except Exception as e:
                logger.error("Failed to send QQ message: %s", e)
    return web.Response(text='{"status":"ok"}', content_type="application/json")


app = web.Application()
app.router.add_post("/alert", handle_alert)


def main():
    logger.info("Alert bridge starting on 127.0.0.1:8081")
    web.run_app(app, host="127.0.0.1", port=8081, print=None)


if __name__ == "__main__":
    main()
