from typing import Any

from nonebot import on_command, on_message
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import Bot as OnebotBot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.rule import to_me
from nonebot.typing import T_State

from src.ext.permission import ADMIN, SUPERUSER
from src.ext.rule import reply
from src.utils.message import ReceivedMessageTracker, SentMessageTracker

from .ask import Ask

SESSION_GROUP = "group_{group_id}_{user_id}"
SESSION_GROUP_PREFIX = "group_{group_id}_"
SESSION_USER = "{user_id}"

record_message = on_message(priority=0, block=False)
record_unhandled_message = on_message(priority=255, block=True)

recall_message = on_command("撤回", aliases={"快撤回"}, rule=to_me(), block=True)
answer_ask = on_message(priority=2, block=True)

check_reply = reply()


def get_session_id(event: MessageEvent) -> tuple[str, str]:
    if isinstance(event, GroupMessageEvent):
        return (SESSION_GROUP.format(group_id=event.group_id,
                                     user_id=event.user_id),
                SESSION_GROUP_PREFIX.format(group_id=event.group_id))
    return SESSION_USER.format(user_id=event.user_id), ""


@Bot.on_called_api
async def handle_api_result(bot: Bot, exception: Exception | None, api: str,
                            data: dict[str, Any], result: Any):
    if exception:
        return

    match api:
        case "send_msg":
            if "group_id" in data:
                session_id = SESSION_GROUP.format(**data)
            else:
                session_id = SESSION_USER.format(**data)
            SentMessageTracker.add(session_id, result["message_id"],
                                   data["message"])


@recall_message.handle()
async def _(bot: Bot, event: MessageEvent, state: T_State):
    session_id, group_prefix = get_session_id(event)

    # directly called without reply specified
    if not await check_reply(bot, event, state):
        message_id = SentMessageTracker.remove(session_id)
        if message_id is not None:
            await bot.delete_msg(message_id=message_id)
        await recall_message.finish()

    # try to recall the replied message
    reply: Reply = state["reply"]
    if str(reply.sender.user_id) != bot.self_id:  # bot.self_id is a string
        await recall_message.finish()
    session_id, group_prefix = get_session_id(event)
    # user exact match
    message_id = SentMessageTracker.remove(session_id, reply.message_id)
    if message_id is not None:
        await bot.delete_msg(message_id=message_id)
        await recall_message.finish()
    perm = SUPERUSER | ADMIN
    if await perm(bot, event):
        message_id = SentMessageTracker.remove_prefix(group_prefix,
                                                      reply.message_id)
        if message_id is not None:
            await bot.delete_msg(message_id=message_id)
            await recall_message.finish()


@record_message.handle()
async def _(event: GroupMessageEvent):
    """Called before all other handlers with priority 0.

    Suppose the message will be handled by other handlers.
    """
    ReceivedMessageTracker.add(event.group_id,
                               event.message_id,
                               event.message,
                               handled=True)
    await record_message.finish()


@record_unhandled_message.handle()
async def _(event: GroupMessageEvent):
    """Called after all other handlers with priority 255.

    If the message goes through all handlers here, it is unhandled.
    """
    ReceivedMessageTracker.add(event.group_id,
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
