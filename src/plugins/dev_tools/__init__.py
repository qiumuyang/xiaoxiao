import json

from nonebot.adapters.onebot.v11.event import Reply
from nonebot.permission import SUPERUSER
from nonebot.typing import T_State

from src.ext.message.segment import MessageSegment
from src.ext.on import on_reply
from src.utils.render_ext.markdown import Markdown

check_message_repr = on_reply("repr", permission=SUPERUSER, block=True)


@check_message_repr.handle()
async def _(state: T_State):
    reply: Reply = state["reply"]
    content = reply.message
    item = json.dumps(MessageSegment.serialize(content),
                      ensure_ascii=False,
                      indent=2)
    markdown_content = f"```json\n{item}\n```"
    image = Markdown(text=markdown_content).render().to_pil()
    await check_message_repr.finish(MessageSegment.image(image))
