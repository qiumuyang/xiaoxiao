import re

import pypinyin
from nonebot import on_command, on_regex
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.params import CommandArg

from src.ext import ratelimit
from src.utils.doc import CommandCategory, command_doc

from .guess import GuessIdiom
from .guess.data import UPDATE_INTERVAL_STR


def _():  # in case of unused imports
    _ = UPDATE_INTERVAL_STR


lim = ratelimit("idiom.guess", type="group", seconds=5)

pinyin_pattern = r"^[a-zA-Z ]{6,}$"
matcher = on_command("猜成语", rule=lim, block=True, force_whitespace=True)
shortcut = on_regex(r"(^[a-zA-Z ]{6,}$)|(^[\u4e00-\u9fa5]{4}\s*$)",
                    rule=lim,
                    block=False)


@matcher.handle()
@command_doc("猜成语", category=CommandCategory.FUN)
async def _(event: GroupMessageEvent, arg_: Message = CommandArg()):
    """
    拼音猜成语 Wordle-like

    Special:
        载入炎国语言模组（龙门粗口已过滤）……拼音字母矩阵已加载。

    Usage:
        {cmd}                  - 开始游戏
        {cmd} `<拼音|成语>`   - 进行一次猜测
        `<合法拼音>`          - 无需指令前缀的快捷猜测
        字母颜色含义：
        * `绿色(✓)` 位置和字母正确
        * `黄色(?)` 存在字母但位置错误
        * `灰色(×)` 不存在字母

    Examples:
        (假设答案是zi qi dong lai)
        >>> 猜成语 yi ge ding lia
                   ×✓ ×× ✓?✓✓ ✓??

        >>> {cmd} 局部坏死

        >>> zhenggehaohuo (可以不加空格)

    Notes:
        - 猜成语进度全群共享，每{UPDATE_INTERVAL_STR}更新一次
        - 来源: [https://github.com/limboy/idiom](https://github.com/limboy/idiom)
           & [https://idiom.limboy.me](https://idiom.limboy.me)
    """
    group_id = event.group_id
    user_id = event.user_id
    guess = GuessIdiom(group_id)
    arg = arg_.extract_plain_text().strip().lower()
    result = None
    if not arg:
        result = await guess.start()
    elif re.match(pinyin_pattern, arg):
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
    if re.fullmatch(pinyin_pattern, arg):
        pinyin = arg
    else:
        matched, pinyin = await guess.match_target(arg)
        if not matched:
            return
    result = await guess.guess(user_id, pinyin, explicit=False)
    if result is not None:
        await shortcut.finish(result)
