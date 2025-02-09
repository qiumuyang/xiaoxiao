from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import CommandArg

from src.ext import MessageSegment

from .load import load_document_image

matcher = on_command("帮助", aliases={"help"}, force_whitespace=True, block=True)


@matcher.handle()
async def _(bot: Bot, event: GroupMessageEvent, arg_: Message = CommandArg()):
    arg = arg_.extract_plain_text().strip()
    if not arg:
        image = load_document_image()
        summary = "帮助总览"
    else:
        image = load_document_image(arg)
        summary = f"帮助-{arg}"
    if image:
        await matcher.finish(MessageSegment.image(image, summary=summary))
    else:
        await matcher.finish("未找到该命令或尚未编写帮助文档")
