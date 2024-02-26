from typing import Any

from nonebot import on_command
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent
from nonebot.rule import to_me

from src.utils.message import SentMessageTracker

SESSION_GROUP = "group_{group_id}_{user_id}"
SESSION_USER = "{user_id}"

recall_message = on_command("撤回", aliases={"快撤回"}, rule=to_me(), block=True)


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
async def _(bot, event: MessageEvent):
    if isinstance(event, GroupMessageEvent):
        session_id = SESSION_GROUP.format(group_id=event.group_id,
                                          user_id=event.user_id)
    else:
        session_id = SESSION_USER.format(user_id=event.user_id)

    message_id = SentMessageTracker.remove(session_id)
    if message_id is not None:
        await bot.delete_msg(message_id=message_id)

    await recall_message.finish()
