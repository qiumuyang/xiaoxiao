from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11.event import Reply
from nonebot.params import CommandArg
from nonebot.typing import T_State

from src.ext import MessageSegment
from src.ext.on import on_reply
from src.utils.doc import CommandCategory, command_doc
from src.utils.render_ext.markdown import Markdown

render_markdown = on_command("markdown",
                             aliases={"渲染"},
                             block=True,
                             force_whitespace=True,
                             priority=2)
render_markdown_reply = on_reply(("渲染", "markdown"), block=True)


@render_markdown.handle()
@command_doc("markdown", aliases={"渲染"}, category=CommandCategory.IMAGE)
async def _(arg: Message = CommandArg()):
    """
    渲染Markdown文本为图片

    Usage:
        {cmd} `<Markdown文本>`  -  渲染文本
        `引用` {cmd}              -  渲染*引用消息*中的文本

    Notes:
        - 暂不支持图片和行内公式
    """
    if content := arg.extract_plain_text():
        image = Markdown(content).render().to_pil()
        await render_markdown.finish(
            MessageSegment.image(image, summary="Markdown"))


@render_markdown_reply.handle()
async def _(state: T_State):
    reply: Reply | None = state.get("reply")
    if not reply:
        return
    if content := reply.message.extract_plain_text():
        image = Markdown(content).render().to_pil()
        await render_markdown_reply.finish(
            MessageSegment.image(image, summary="Markdown"))
