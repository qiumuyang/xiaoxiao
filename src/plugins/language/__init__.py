import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Annotated, Any

from nonebot import on_command, on_message
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import Bot as OnebotBot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.params import Depends
from nonebot.rule import to_me
from nonebot.typing import T_State

from src.ext.permission import ADMIN, SUPERUSER
from src.ext.rule import RateLimit, RateLimiter, ratelimit, reply
from src.utils.message import ReceivedMessageTracker, SentMessageTracker

from .ask import Ask
from .interact import Interact

record_message = on_message(priority=0, block=False)
record_unhandled_message = on_message(priority=255, block=True)
interact_with = on_message(priority=10, block=False)

recall_message = on_command("撤回", aliases={"快撤回"}, rule=to_me(), block=True)
answer_ask = on_command("问",
                        force_whitespace=False,
                        priority=2,
                        block=True,
                        rule=ratelimit("问", type="user", seconds=2))
message_rank = on_command("发言排行",
                          force_whitespace=True,
                          block=True,
                          rule=ratelimit("发言排行", type="group", seconds=5))

check_reply = reply()


@Bot.on_called_api
async def handle_api_result(bot: Bot, exception: Exception | None, api: str,
                            data: dict[str, Any], result: Any):
    if exception:
        return

    match api:
        case "send_msg":
            session_id = SentMessageTracker.get_session_id(data)
            await SentMessageTracker.add(session_id, result["message_id"],
                                         data["message"])


@recall_message.handle()
async def _(bot: Bot, event: MessageEvent, state: T_State):
    session_id, group_prefix = SentMessageTracker.get_session_id_or_prefix(
        event)

    # directly called without reply specified
    if not await check_reply(bot, event, state):
        message_id = await SentMessageTracker.remove(session_id)
        if message_id is not None:
            await bot.delete_msg(message_id=message_id)
        await recall_message.finish()

    # try to recall the replied message
    reply: Reply = state["reply"]
    if str(reply.sender.user_id) != bot.self_id:  # bot.self_id is a string
        await recall_message.finish()
    session_id, group_prefix = SentMessageTracker.get_session_id_or_prefix(
        event)

    # user exact match
    message_id = await SentMessageTracker.remove(session_id, reply.message_id)
    if message_id is not None:
        await bot.delete_msg(message_id=message_id)
        await recall_message.finish()
    perm = SUPERUSER | ADMIN
    if await perm(bot, event):
        message_id = await SentMessageTracker.remove_prefix(
            group_prefix, reply.message_id)
        if message_id is not None:
            await bot.delete_msg(message_id=message_id)
            await recall_message.finish()


@record_message.handle()
async def _(event: GroupMessageEvent):
    """Called before all other handlers with priority 0.

    Suppose the message will be handled by other handlers.
    """
    await ReceivedMessageTracker.add(event.user_id,
                                     event.group_id,
                                     event.message_id,
                                     event.message,
                                     handled=True)
    # should not finish here


@record_unhandled_message.handle()
async def _(event: GroupMessageEvent):
    """Called after all other handlers with priority 255.

    If the message goes through all handlers here, it is unhandled.
    """
    await ReceivedMessageTracker.add(event.user_id,
                                     event.group_id,
                                     event.message_id,
                                     event.message,
                                     handled=False)
    await record_unhandled_message.finish()


@answer_ask.handle()
async def _(bot: OnebotBot, event: GroupMessageEvent):
    result = await Ask(bot, event.group_id,
                       event.message.extract_plain_text()).answer()
    if result:
        await answer_ask.finish(result)


@message_rank.handle()
async def _(bot: OnebotBot, event: GroupMessageEvent):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    messages = await ReceivedMessageTracker.find(group_id=event.group_id,
                                                 since=today)
    user_messages = defaultdict(int)
    for message in messages:
        user_messages[message.user_id] += 1
    user_messages = sorted(user_messages.items(), key=lambda x: -x[1])

    group_info = await bot.get_group_info(group_id=event.group_id,
                                          no_cache=True)
    group_name = group_info["group_name"]
    date = today.strftime("%m-%d")
    result = f"{group_name} {date} 发言排行\n"
    if not user_messages:
        await message_rank.finish("今天还没有人发言哦")
    # top = min(10, group_info["member_count"] // 2)
    # member_count seems problematic for now
    top = 10
    top_uid, top_messages = zip(*user_messages[:top])
    tasks = [
        bot.get_group_member_info(group_id=event.group_id, user_id=user_id)
        for user_id in top_uid
    ]
    members = await asyncio.gather(*tasks)
    # temporary fix for the member name problem
    prefix = "\x08%ĀĀ\x07Ñ\n\x08\x12\x06"
    suffix = "\x10\x00"

    def make_name(member: dict):
        name = member["card"] or member["nickname"]
        return name.strip().removeprefix(prefix).removesuffix(suffix)

    ranking = "\n".join(
        f"{i}. {make_name(member)} {count}"
        for i, (member, count) in enumerate(zip(members, top_messages), 1))
    await message_rank.finish(result + ranking)


@interact_with.handle()
async def _(
    event: GroupMessageEvent,
    ratelimit: Annotated[
        RateLimiter,
        Depends(RateLimit("关键词回复", type="group", seconds=10))],
):
    if message := event.message.extract_plain_text().strip():
        resp = await Interact.response(event.group_id, message)
        if resp and ratelimit.try_acquire():
            await interact_with.send(resp)
