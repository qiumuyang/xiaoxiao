import re

from nonebot import on_command, on_regex
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.params import CommandArg

from src.utils.doc import CommandCategory, command_doc

from .feihua.game import FeiHua

matcher = on_command("飞花令", block=True, force_whitespace=True)
shortcut = on_regex(r"^[\u4e00-\u9fa5]{2,}", block=False)
single_hans = re.compile(r"[\u4e00-\u9fa5]")


@matcher.handle()
@command_doc("飞花令", category=CommandCategory.FUN)
async def _(event: GroupMessageEvent, arg_: Message = CommandArg()):
    """
    进行飞花令游戏

    Special:
        检测到异常声纹记录。正在执行多维结构分析

        ——分类显示为“诗词赋”炎国古文体
        （注：与魏彦吾阁下的私人藏书库第VIII区加密文档存在12.3%关联性）

    Usage:
        {cmd}             - 以**随机题目**开始游戏
        {cmd} `<单字>`    - 以**指定题目**开始游戏
        {cmd} `<诗词>`    - 进行回答
        {cmd} `结束`      - 结束游戏
        `<诗词>`          - 无需指令前缀的快捷回答
        说出包含指定字的诗词句即可得分，不可重复。

    Notes:
        - 诗词来源于网络，可能出现*错字*或*错误来源*
        - 为防止误触发，快捷回答仅在成功或回答重复时响应
    """
    group_id = event.group_id
    user_id = event.user_id
    game = FeiHua(group_id)

    arg = arg_.extract_plain_text().strip()
    # TODO: add custom keyword support
    if not arg:
        result = await game.start([])
    elif arg == "结束":
        result = await game.stop()
    elif len(arg) == 1 and single_hans.match(arg):
        result = await game.start([arg])
    else:
        result = await game.answer(user_id, arg, explicit=True)
    await matcher.finish(result)


@shortcut.handle()
async def _(event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    game = FeiHua(group_id)
    arg = event.get_message().extract_plain_text().strip()
    result = await game.answer(user_id, arg, explicit=False)
    if result is not None:
        await shortcut.finish(result)
