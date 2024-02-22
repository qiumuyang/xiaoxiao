from io import BytesIO

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment

from .fortune import get_fortune
from .render import FortuneRender

matcher = on_command("今日运势", aliases={"jrys"})


@matcher.handle()
async def _(event: MessageEvent):
    user_id = event.user_id
    user_name = event.sender.card or event.sender.nickname or str(user_id)
    fortune = get_fortune(user_id, user_name)
    image = FortuneRender.render(fortune)
    io = BytesIO()
    image.save(io, format="PNG")
    io.seek(0)
    await matcher.finish(MessageSegment.image(io))
