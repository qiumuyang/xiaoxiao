from nonebot import on_command, on_regex
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.params import CommandArg

from .feihua.game import FeiHua

matcher = on_command("飞花令", block=True, force_whitespace=True)
shortcut = on_regex(r"^[\u4e00-\u9fa5]{2,}", block=False)


@matcher.handle()
async def _(event: GroupMessageEvent, arg_: Message = CommandArg()):
    group_id = event.group_id
    user_id = event.user_id
    game = FeiHua(group_id)

    arg = arg_.extract_plain_text().strip()
    # TODO: add custom keyword support
    if not arg:
        result = await game.start([])
    elif arg == "结束":
        result = await game.stop()
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
