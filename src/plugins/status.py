import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import TypedDict

from nonebot import CommandGroup
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.permission import SUPERUSER

from src.ext import MessageSegment, get_group_member_name, ratelimit
from src.utils.doc import CommandCategory, command_doc
from src.utils.message import ReceivedMessageTracker as RMT
from src.utils.message import SentMessageTracker as SMT
from src.utils.observability.vm import VMClient
from src.utils.observability.wrappers import with_metric
from src.utils.render_ext.markdown import Markdown

_start_time = time.time()

_NA = "N/A"


class Status(TypedDict):
    cpu: str
    memory: str
    memory_mongo: str
    memory_free: str
    message_sent: int
    message_received: int
    commands_handled: int
    running_time: timedelta
    load_1: str
    load_5: str
    load_15: str
    sys_uptime: str
    disk_avail: str
    disk_total: str
    mongo_up: str
    mongo_connections: str
    mongo_ops: str


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
        load1_task = VMClient.query_value("node_load1{job=\"node\"}")
        load5_task = VMClient.query_value("node_load5{job=\"node\"}")
        load15_task = VMClient.query_value("node_load15{job=\"node\"}")
        sys_uptime_task = VMClient.query_value(
            "(time() - node_boot_time_seconds{job=\"node\"}) / 86400"
        )
        disk_avail_task = VMClient.query_value(
            "node_filesystem_avail_bytes{mountpoint=\"/\",fstype!=\"\"} / 1073741824"
        )
        disk_total_task = VMClient.query_value(
            "node_filesystem_size_bytes{mountpoint=\"/\",fstype!=\"\"} / 1073741824"
        )
        mongo_up_task = VMClient.query_value("mongodb_up")
        mongo_conn_task = VMClient.query_value(
            "mongodb_ss_connections{conn_type=\"current\"}"
        )
        mongo_ops_task = VMClient.query_value(
            "rate(mongodb_top_commands_count[5m])"
        )

        sent_task = SMT.count(group_id=group_id, since=datetime.fromtimestamp(_start_time))
        recv_task = RMT.count(group_id=group_id or [], since=datetime.fromtimestamp(_start_time))
        cmd_task = RMT.count(group_id=group_id or [], since=datetime.fromtimestamp(_start_time), handled=True)

        (cpu, memory, memory_free, memory_mongo,
         load1, load5, load15, sys_uptime,
         disk_avail, disk_total,
         mongo_up, mongo_conn, mongo_ops,
         sent, recv, cmd) = await asyncio.gather(
            cpu_task, mem_task, mem_free_task, mem_mongo_task,
            load1_task, load5_task, load15_task, sys_uptime_task,
            disk_avail_task, disk_total_task,
            mongo_up_task, mongo_conn_task, mongo_ops_task,
            sent_task, recv_task, cmd_task,
        )

        def _fmt(val: float | None) -> str:
            return f"{val:.0f}" if val is not None else _NA

        def _f2(val: float | None) -> str:
            return f"{val:.2f}" if val is not None else _NA

        def _mongo_status(val: float | None) -> str:
            if val is None:
                return _NA
            return "运行中" if int(val) == 1 else "已停止"

        return {
            "cpu": f"{_fmt(cpu)}%",
            "memory": f"{_fmt(memory)}MB",
            "memory_mongo": f"{_fmt(memory_mongo)}MB",
            "memory_free": f"{_fmt(memory_free)}MB",
            "load_1": _f2(load1),
            "load_5": _f2(load5),
            "load_15": _f2(load15),
            "sys_uptime": _fmt(sys_uptime),
            "disk_avail": _fmt(disk_avail),
            "disk_total": _fmt(disk_total),
            "mongo_up": _mongo_status(mongo_up),
            "mongo_connections": _fmt(mongo_conn),
            "mongo_ops": _fmt(mongo_ops),
            "message_sent": sent,
            "message_received": recv,
            "commands_handled": cmd,
            "running_time": running_time,
        }

    @classmethod
    def format(cls, status: Status) -> str:
        tm = str(status["running_time"]).split(".")[0]

        load_ok = status["load_1"] != _NA
        load = (
            f"{status['load_1']} / {status['load_5']} / {status['load_15']}"
            if load_ok
            else _NA
        )

        da = status["disk_avail"]
        dt = status["disk_total"]
        if da != _NA and dt != _NA:
            pct = 100 - int(float(da) / float(dt) * 100)
            disk = f"{da}GB / {dt}GB ({pct}%)"
        else:
            disk = _NA

        su = status["sys_uptime"]
        sys_uptime = f"{su}天" if su != _NA else _NA

        system = [
            "| 系统 |  |",
            "|------|--|",
            f"| CPU | {status['cpu']} |",
            f"| 负载(1/5/15m) | {load} |",
            f"| 内存 | {status['memory']} (可用 {status['memory_free']}) |",
            f"| 磁盘 | {disk} |",
            f"| 系统运行 | {sys_uptime} |",
            f"| Bot运行 | {tm} |",
        ]

        mo = status["mongo_ops"]
        mongo_ops = f"{mo}/s" if mo != _NA else _NA

        mongo = [
            "| MongoDB |  |",
            "|---------|--|",
            f"| 状态 | {status['mongo_up']} |",
            f"| 内存 | {status['memory_mongo']} |",
            f"| 连接数 | {status['mongo_connections']} |",
            f"| 操作 | {mongo_ops} |",
        ]

        messages = [
            "| 消息 |  |",
            "|------|--|",
            f"| 发送 | {status['message_sent']} |",
            f"| 接收 | {status['message_received']} |",
            f"| 指令处理 | {status['commands_handled']} |",
        ]

        return "\n\n".join(
            "\n".join(t) for t in [system, mongo, messages]
        )


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
    md = f"# {name}\n\n" + StatusMonitor.format(st)
    image = Markdown(md).render().to_pil()
    await stat_overview.finish(MessageSegment.image(image, summary="status"))


@stat_this.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    st = await StatusMonitor.status(event.group_id)
    group = await bot.get_group_info(group_id=event.group_id)
    name = await get_group_member_name(
        group_id=event.group_id, user_id=int(bot.self_id)
    )
    md = f"# {name} ({group['group_name']})\n\n" + StatusMonitor.format(st)
    image = Markdown(md).render().to_pil()
    await stat_this.finish(MessageSegment.image(image, summary="status"))


@stat_all.handle()
async def _(bot: Bot):
    group_list = await bot.get_group_list()
    status_list = await asyncio.gather(
        *(StatusMonitor.status(group["group_id"]) for group in group_list)
    )
    global_status = await StatusMonitor.status()
    info_stat = sorted(
        zip(group_list, status_list, strict=False),
        key=lambda x: (x[1]["message_sent"], x[1]["message_received"]),
        reverse=True,
    )[:5]

    name = os.getenv("BOT_NAME", "鸮鸮")
    md = f"# {name}\n\n" + StatusMonitor.format(global_status)

    group_lines = []
    for group_info, stat in info_stat:
        if not stat["message_received"]:
            continue
        gname = group_info["group_name"]
        gid = group_info["group_id"]
        sent, recv = stat["message_sent"], stat["message_received"]
        group_lines.append(f"| {gname} ({gid}) | {sent}/{recv} |")

    if group_lines:
        groups_table = [
            "| 群组 |  |",
            "|------|--|",
            *group_lines,
        ]
        md += "\n\n" + "\n".join(groups_table)

    image = Markdown(md).render().to_pil()
    await stat_all.finish(MessageSegment.image(image, summary="status"))
