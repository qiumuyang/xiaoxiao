"""Alertmanager webhook → OneBot QQ group message with SMTP fallback."""
import asyncio
import json
import logging
import os
import smtplib
from email.mime.text import MIMEText

import aiohttp
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alert_bridge")

ONEBOT_URL = os.getenv("ONEBOT_URL", "http://127.0.0.1:3000")
GROUP_ID = int(os.getenv("ALERT_GROUP_ID", "0"))
AT_QQ = int(os.getenv("ALERT_AT_QQ", "0"))

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_TO = os.getenv("SMTP_TO", "")

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


def send_email(subject: str, body: str) -> bool:
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_TO]):
        logger.warning("SMTP not configured, skip email fallback")
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = SMTP_TO
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, [SMTP_TO], msg.as_string())
        logger.info("Email sent to %s: %s", SMTP_TO, subject)
        return True
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False


async def send_qq_message(
    session: aiohttp.ClientSession, message: str
) -> tuple[bool, str]:
    try:
        resp = await session.post(
            f"{ONEBOT_URL}/send_group_msg",
            json={"group_id": GROUP_ID, "message": message},
        )
        data = await resp.json()
        if data.get("status") == "ok" and data.get("retcode") == 0:
            return True, str(data)
        return False, str(data)
    except Exception as e:
        return False, str(e)


async def handle_alert(request: web.Request) -> web.Response:
    body = await request.json()
    logger.info("Received alert hook: %d alerts", len(body.get("alerts", [])))
    overall_ok = True
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10)
    ) as session:
        for alert in body.get("alerts", []):
            if alert["status"] not in ("firing", "resolved"):
                continue
            message = format_alert(alert)
            summary = alert["annotations"].get("summary", alert["labels"]["alertname"])
            ok, result = await send_qq_message(session, message)
            logger.info("QQ send: ok=%s result=%s", ok, result)
            if not ok:
                email_subject = f"[鸮鸮 告警] {summary}（QQ发送失败）"
                email_body = (
                    f"QQ 群消息发送失败，以下为备援通知：\n\n"
                    f"告警名称: {summary}\n"
                    f"严重程度: {alert['labels'].get('severity', '')}\n"
                    f"详情: {alert['annotations'].get('description', '')}\n"
                    f"QQ 发送结果: {result}\n"
                )
                if await asyncio.to_thread(send_email, email_subject, email_body):
                    logger.info("Email fallback sent for alert: %s", summary)
                else:
                    overall_ok = False
                    logger.error(
                        "Both QQ and email failed for alert: %s", summary
                    )
    if not overall_ok:
        return web.Response(
            text=json.dumps({"status": "partial_failure"}),
            content_type="application/json",
            status=500,
        )
    return web.Response(text='{"status":"ok"}', content_type="application/json")


app = web.Application()
app.router.add_post("/alert", handle_alert)


def main():
    logger.info("Alert bridge starting on 127.0.0.1:8081")
    web.run_app(app, host="127.0.0.1", port=8081, print=None)


if __name__ == "__main__":
    main()
