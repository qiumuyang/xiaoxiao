import re

import pypinyin
from nonebot import on_command, on_regex
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.params import CommandArg

from src.ext import ratelimit

from .guess import GuessIdiom

lim = ratelimit("idiom.guess", type="group", seconds=5)

pattern = r"^[a-zA-Z ]{6,}$"
matcher = on_command("猜成语", rule=lim, block=True, force_whitespace=True)
shortcut = on_regex(pattern, rule=lim, block=False)


@matcher.handle()
async def _(event: GroupMessageEvent, arg_: Message = CommandArg()):
    group_id = event.group_id
    user_id = event.user_id
    guess = GuessIdiom(group_id)
    arg = arg_.extract_plain_text().strip().lower()
    result = None
    if not arg:
        result = await guess.start()
    elif re.match(pattern, arg):
        result = await guess.guess(user_id, arg, explicit=True)
    else:
        result = await guess.guess(user_id,
                                   " ".join(pypinyin.lazy_pinyin(arg)),
                                   explicit=False)
    await matcher.finish(result)


@shortcut.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    guess = GuessIdiom(group_id)
    arg = event.get_message().extract_plain_text().strip().lower()
    result = await guess.guess(user_id, arg, explicit=False)
    if result is not None:
        await shortcut.finish(result)
