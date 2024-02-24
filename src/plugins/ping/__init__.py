from nonebot import on_command
from nonebot.matcher import Matcher

ping = on_command("ping", block=True)


@ping.handle()
async def _(matcher: Matcher):
    await matcher.finish("Pong!")
