from typing import cast

from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent
from nonebot.adapters.onebot.v11.event import Reply

prefixes = [
    "\x08%ĀĀ\x07Ñ\n\x08\x12\x06",
    "\u0025\u0100\u0100\u2407\u00d6\u000a\u0011\u0012\u000f"
]
suffix = "\x10\x00"


def fix_name(name: str) -> str:
    name = name.strip().removesuffix(suffix)
    for prefix in prefixes:
        name = name.removeprefix(prefix)
    return name


async def get_user_name(event: MessageEvent | Reply,
                        *,
                        bot: Bot | None = None) -> str:
    bot = bot or cast(Bot, get_bot())
    if isinstance(event, GroupMessageEvent):
        return await get_group_member_name(group_id=event.group_id,
                                           user_id=event.user_id,
                                           bot=bot)
    name = event.sender.card or event.sender.nickname  # or str(event.user_id)
    if isinstance(event, Reply):
        name = name or str(event.sender.user_id)
    else:
        name = name or str(event.user_id)
    return fix_name(name)


async def get_group_member_name(
    *,
    group_id: int,
    user_id: int,
    bot: Bot | None = None,
) -> str:
    bot = bot or cast(Bot, get_bot())
    member_info = await bot.get_group_member_info(group_id=group_id,
                                                  user_id=user_id)
    name = member_info["card"] or member_info["nickname"] or str(user_id)
    return fix_name(name)


async def list_group_member_names(
    *,
    group_id: int,
    bot: Bot | None = None,
) -> list[str]:
    bot = bot or cast(Bot, get_bot())
    member_list = await bot.get_group_member_list(group_id=group_id)
    names = []
    for member in member_list:
        name = member["card"] or member["nickname"]
        if name:
            names.append(fix_name(name))
    return names
