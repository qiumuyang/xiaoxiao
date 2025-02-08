from nonebot import on_command
from nonebot.matcher import Matcher

from src.utils.doc import CommandCategory, command_doc

ping = on_command("ping", block=True, force_whitespace=True)


@ping.handle()
@command_doc("ping", category=CommandCategory.UTILITY)
async def _(matcher: Matcher):
    """
    检测Bot是否在线

    Special:
        激活生存确认协议……正在发送莱茵生命标准心跳包……
    """
    await matcher.finish("Pong!")
