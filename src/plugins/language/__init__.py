import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any

from nonebot import CommandGroup, on_command, on_message
from nonebot.adapters import Bot, Message
from nonebot.adapters.onebot.v11 import Bot as OnebotBot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot.typing import T_State

from src.ext.message import MessageSegment
from src.ext.permission import ADMIN, SUPERUSER
from src.ext.rule import RateLimit, RateLimiter, enabled, ratelimit, reply
from src.utils.message import ReceivedMessageTracker, SentMessageTracker

from .ask import Ask
from .config import (RandomResponseConfig, toggle_group_response_request,
                     toggle_user_response)
from .history import History
from .interact import RandomResponse

record_message = on_message(priority=0, block=False)
random_response = on_message(priority=10,
                             block=False,
                             rule=enabled(RandomResponseConfig))
record_unhandled_message = on_message(priority=255, block=True)

recall_message = on_command("撤回", aliases={"快撤回"}, rule=to_me(), block=True)
answer_ask = on_command("问",
                        force_whitespace=False,
                        priority=2,
                        block=True,
                        rule=ratelimit("问", type="user", seconds=2))
message_rank = on_command("发言排行",
                          force_whitespace=True,
                          block=True,
                          rule=ratelimit("发言排行", type="group", seconds=15))
disable_response = on_command("闭嘴",
                              aliases={"闭菊"},
                              force_whitespace=True,
                              block=True)
enable_response = on_command("张嘴",
                             aliases={"张菊", "开菊", "开嘴"},
                             force_whitespace=True,
                             block=True)

message_trace = CommandGroup("trace", block=True)
trace_single = message_trace.command(
    tuple(),
    force_whitespace=True,
    rule=ratelimit("trace_single", type="group", seconds=5),
)
trace_search = message_trace.command(
    "search",
    force_whitespace=True,
    rule=ratelimit("trace_search", type="group", seconds=5),
)

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
    result = await Ask(bot, event.group_id, event.message).answer()
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


@random_response.handle()
async def _(event: GroupMessageEvent,
            ratelimit: RateLimiter = RateLimit("随机回复",
                                               type="group",
                                               seconds=10)):
    resp = await RandomResponse.response(event.group_id, event.message)
    if resp:
        resp = MessageSegment.normalize(resp)
        if resp and ratelimit.try_acquire():
            await random_response.send(resp)


@trace_single.handle()
async def _(bot: OnebotBot,
            event: GroupMessageEvent,
            arg: Message = CommandArg()):
    if (input := arg.extract_plain_text()) and input.isdigit():
        index = int(input)
    else:
        index = 1

    await trace_single.finish(await History.find_single_message(bot,
                                                                event.group_id,
                                                                index=index))


@trace_search.handle()
async def _(bot: OnebotBot,
            event: GroupMessageEvent,
            arg: Message = CommandArg()):
    senders = []
    keywords = []
    for seg in arg:
        segment = MessageSegment.from_onebot(seg)
        if segment.is_at():
            senders.append(segment.extract_at())
        elif segment.is_text():
            keywords.extend(segment.extract_text_args())

    await trace_single.finish(await History.find(bot,
                                                 event.group_id,
                                                 senders=senders,
                                                 keywords=keywords))


@disable_response.handle()
async def _(event: GroupMessageEvent,
            notice_lim: RateLimiter = RateLimit("随机回复关闭提示",
                                                type="group",
                                                seconds=600)):
    if event.is_tome():
        if await toggle_user_response(user_id=event.user_id, enabled=False):
            await disable_response.finish("鸮鸮对你的随机回复已关闭")
        return
    result = await toggle_group_response_request(user_id=event.user_id,
                                                 group_id=event.group_id,
                                                 enabled=False)
    if type(result) is int:
        requests = RandomResponseConfig.num_reqs_to_toggle
        prompt = f"正在关闭鸮鸮的随机回复，进度 {result}/{requests}"
        if notice_lim.try_acquire():
            prompt += "\n（@鸮鸮 可以对个人关闭）"
        await disable_response.finish(prompt)
    if result:
        await disable_response.finish("鸮鸮的随机回复已关闭")


@enable_response.handle()
async def _(event: GroupMessageEvent):
    user_toggled = await toggle_user_response(user_id=event.user_id,
                                              enabled=True)
    result = await toggle_group_response_request(user_id=event.user_id,
                                                 group_id=event.group_id,
                                                 enabled=True)
    requests = RandomResponseConfig.num_reqs_to_toggle
    if user_toggled:
        prompt = "鸮鸮对你的随机回复已开启"
        if type(result) is int:  # group disabled
            prompt += f"\n群内未开启，进度 {result}/{requests}"
        await enable_response.finish(prompt)
    if type(result) is int:
        prompt = f"正在开启鸮鸮的随机回复，进度 {result}/{requests}"
        await enable_response.finish(prompt)
    if result is True:
        await enable_response.finish("鸮鸮的随机回复已开启")
