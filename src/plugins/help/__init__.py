from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from src.ext import MessageExtension
from src.utils.doc import DocManager

matcher = on_command("帮助",
                     aliases={"help"},
                     force_whitespace=True,
                     block=True,
                     permission=SUPERUSER)


@matcher.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg_: Message = CommandArg()):
    arg = arg_.extract_plain_text().strip()
    doc = DocManager.get(arg)
    if doc:
        message = await MessageExtension.markdown(doc.export_markdown(),
                                                  int(bot.self_id),
                                                  "鸮鸮",
                                                  bot=bot)
        await bot.send_group_forward_msg(messages=message,
                                         group_id=event.group_id)
        await matcher.finish()
    else:
        await matcher.finish("未找到该命令")
