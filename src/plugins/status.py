import asyncio
from datetime import datetime, timedelta
from typing import TypedDict

import psutil
from nonebot import CommandGroup, get_driver
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.permission import SUPERUSER

from src.ext import ratelimit
from src.utils.message import ReceivedMessageTracker as RMT
from src.utils.message import SentMessageTracker as SMT


class Status(TypedDict):
    cpu: int
    memory: int
    message_sent: int
    message_received: int
    commands_handled: int
    running_time: timedelta


class Checker:

    driver = get_driver()

    @classmethod
    async def status(cls, group_id: int | None = None) -> Status:
        proc = psutil.Process()
        cpu = round(proc.cpu_percent())
        memory = proc.memory_info().rss // 1024 // 1024  # MB
        create_time = datetime.fromtimestamp(proc.create_time())
        running_time = datetime.now() - create_time

        sent_task = SMT.count(group_id=group_id, since=create_time)
        recv_task = RMT.count(group_id=group_id or [], since=create_time)
        cmd_task = RMT.count(group_id=group_id or [],
                             since=create_time,
                             handled=True)

        sent, recv, cmd = await asyncio.gather(sent_task, recv_task, cmd_task)
        return {
            "cpu": cpu,
            "memory": memory,
            "message_sent": sent,
            "message_received": recv,
            "commands_handled": cmd,
            "running_time": running_time,
        }

    @classmethod
    def format(cls, status: Status) -> str:
        tm = str(status["running_time"]).split(".")[0]  # remove milliseconds
        fmt = ("Running Time: {tm}\n"
               "CPU: {cpu}%\n"
               "Mem: {memory}MB\n"
               "Messages (Sent/Recv): {message_sent}/{message_received}\n"
               "Handle Commands: {commands_handled}")
        return fmt.format(tm=tm, **status)


ratelimit = ratelimit("status", "group", seconds=10)
stat = CommandGroup(cmd="status", block=True)
stat_overview = stat.command(tuple(), rule=ratelimit, force_whitespace=True)
stat_this = stat.command("this", rule=ratelimit, force_whitespace=True)
stat_all = stat.command("all", force_whitespace=True, permission=SUPERUSER)


@stat_overview.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    st = await Checker.status()
    mem = await bot.get_group_member_info(group_id=event.group_id,
                                          user_id=int(bot.self_id))
    name = mem["card"] or mem["nickname"]
    prefix = f"[{name}]\n"
    await stat_overview.finish(prefix + Checker.format(st))


@stat_this.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    st = await Checker.status(event.group_id)
    mem = await bot.get_group_member_info(group_id=event.group_id,
                                          user_id=int(bot.self_id))
    group = await bot.get_group_info(group_id=event.group_id)
    name = mem["card"] or mem["nickname"]
    prefix = f"[{name}] ({group['group_name']})\n"
    await stat_this.finish(prefix + Checker.format(st))


@stat_all.handle()
async def _(bot: Bot):
    group_list = await bot.get_group_list()
    status_list = await asyncio.gather(*(Checker.status(group["group_id"])
                                         for group in group_list))
    global_status = await Checker.status()
    # top 5 groups with the most messages
    info_stat = sorted(zip(group_list, status_list),
                       key=lambda x:
                       (x[1]["message_sent"], x[1]["message_received"]),
                       reverse=True)[:5]
    msg = Checker.format(global_status)
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
