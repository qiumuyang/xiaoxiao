from typing import Any

from nonebot import on_command
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.rule import to_me
from nonebot.typing import T_State

from src.ext.permission import ADMIN, SUPERUSER
from src.ext.rule import reply
from src.utils.message import SentMessageTracker

SESSION_GROUP = "group_{group_id}_{user_id}"
SESSION_GROUP_PREFIX = "group_{group_id}_"
SESSION_USER = "{user_id}"

recall_message = on_command("撤回", aliases={"快撤回"}, rule=to_me(), block=True)
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
            SentMessageTracker.add(session_id, result["message_id"])


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
