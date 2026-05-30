import asyncio
import time
from datetime import datetime, timedelta
from typing import TypedDict

from nonebot import CommandGroup
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.permission import SUPERUSER

from src.ext import get_group_member_name, ratelimit
from src.utils.doc import CommandCategory, command_doc
from src.utils.message import ReceivedMessageTracker as RMT
from src.utils.message import SentMessageTracker as SMT
from src.utils.observability.vm import VMClient
from src.utils.observability.wrappers import with_metric

_start_time = time.time()


class Status(TypedDict):
    cpu: str
    memory: str
    memory_mongo: str
    memory_free: str
    message_sent: int
    message_received: int
    commands_handled: int
    running_time: timedelta


class StatusMonitor:
    @classmethod
    async def status(cls, group_id: int | None = None) -> Status:
        running_time = datetime.now() - datetime.fromtimestamp(_start_time)

        cpu_task = VMClient.query_value(
            "100 - avg(rate(node_cpu_seconds_total{mode=\"idle\", job=\"node\"}[2m])) * 100"
        )
        mem_task = VMClient.query_value(
            "process_resident_memory_bytes{job=\"xiaoxiao\"} / 1024 / 1024"
        )
        mem_free_task = VMClient.query_value(
            "node_memory_MemAvailable_bytes{job=\"node\"} / 1024 / 1024"
        )
        mem_mongo_task = VMClient.query_value(
            "namedprocess_namegroup_memory_bytes{groupname=\"mongod\", memtype=\"resident\"} / 1024 / 1024"
        )

        sent_task = SMT.count(group_id=group_id, since=datetime.fromtimestamp(_start_time))
        recv_task = RMT.count(group_id=group_id or [], since=datetime.fromtimestamp(_start_time))
        cmd_task = RMT.count(group_id=group_id or [], since=datetime.fromtimestamp(_start_time), handled=True)

        cpu, memory, memory_free, memory_mongo, sent, recv, cmd = await asyncio.gather(
            cpu_task, mem_task, mem_free_task, mem_mongo_task,
            sent_task, recv_task, cmd_task,
        )

        def _fmt(val: float | None) -> str:
            return f"{val:.0f}" if val is not None else "N/A"

        return {
            "cpu": f"{_fmt(cpu)}%",
            "memory": f"{_fmt(memory)}MB",
            "memory_mongo": f"{_fmt(memory_mongo)}MB",
            "memory_free": f"{_fmt(memory_free)}MB",
            "message_sent": sent,
            "message_received": recv,
            "commands_handled": cmd,
            "running_time": running_time,
        }

    @classmethod
    def format(cls, status: Status) -> str:
        tm = str(status["running_time"]).split(".")[0]  # remove milliseconds
        fmt = (
            "Uptime: {tm}\n"
            "CPU: {cpu}\n"
            "Mem: {memory} (Free: {memory_free})\n"
            "Mongo: {memory_mongo}\n"
            "Messages (Sent/Recv): {message_sent}/{message_received}\n"
            "Handle Commands: {commands_handled}"
        )
        return fmt.format(tm=tm, **status)


ratelimit = ratelimit("status", "group", seconds=10)
stat = CommandGroup(cmd="status", block=True)


stat_overview = with_metric(
    stat.command(tuple(), rule=ratelimit, force_whitespace=True), label="status"
)

stat_this = with_metric(
    stat.command("this", rule=ratelimit, force_whitespace=True), label="status"
)

stat_all = with_metric(
    stat.command("all", force_whitespace=True, permission=SUPERUSER), label="status"
)


@stat_overview.handle()
@command_doc("status", category=CommandCategory.UTILITY)
async def _(bot: Bot, event: GroupMessageEvent):
    """
    检查{bot}运行状态

    Usage:
        {cmd}      - 运行状态概览
        {cmd}.this - 本群运行状态
    """
    st = await StatusMonitor.status()
    name = await get_group_member_name(
        group_id=event.group_id, user_id=int(bot.self_id)
    )
    prefix = f"[{name}]\n"
    await stat_overview.finish(prefix + StatusMonitor.format(st))


@stat_this.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    st = await StatusMonitor.status(event.group_id)
    group = await bot.get_group_info(group_id=event.group_id)
    name = await get_group_member_name(
        group_id=event.group_id, user_id=int(bot.self_id)
    )
    prefix = f"[{name}] ({group['group_name']})\n"
    await stat_this.finish(prefix + StatusMonitor.format(st))


@stat_all.handle()
async def _(bot: Bot):
    group_list = await bot.get_group_list()
    status_list = await asyncio.gather(
        *(StatusMonitor.status(group["group_id"]) for group in group_list)
    )
    global_status = await StatusMonitor.status()
    # top 5 groups with the most messages
    info_stat = sorted(
        zip(group_list, status_list, strict=False),
        key=lambda x: (x[1]["message_sent"], x[1]["message_received"]),
        reverse=True,
    )[:5]
    msg = StatusMonitor.format(global_status)
    lines = []
    for group_info, stat in info_stat:
        if not stat["message_received"]:
            continue
        group_name = group_info["group_name"]
        group_id = group_info["group_id"]
        sent, recv = stat["message_sent"], stat["message_received"]
        lines.append(f"{group_name} ({group_id}): {sent}/{recv}")

    if lines:
        msg += "\n\n" + "\n".join(lines)
    await stat_all.finish(msg)
