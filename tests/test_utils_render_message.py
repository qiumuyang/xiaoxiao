from pathlib import Path

import pytest
from nonebot.adapters.onebot.v11 import Message as MessageObject
from PIL import Image

from src.ext import MessageSegment
from src.utils.render import Alignment
from src.utils.render_ext.message import Conversation, MessageRender


def placeholder(width: int, height: int) -> Image.Image:
    # r = requests.get(f"https://placehold.co/{width}x{height}.png")
    # r.raise_for_status()
    # return Image.open(BytesIO(r.content))
    return Image.new("RGBA", (width, height), (255, 255, 255, 0))


@pytest.mark.asyncio
async def test_render_message():
    out = Path("render-test/message")
    out.mkdir(parents=True, exist_ok=True)

    avatar = placeholder(256, 256)

    testcases = [
        ("Hello, world!", "nickname", "start", "w-nickname"),
        ("Hello, world!", "", "start", "wo-nickname"),
        ("Hello, world!", "nickname", "end", "align-end"),
        ("Hello, world!", "", "end", "align-end-wo-nickname"),
        ("A quick brown fox jumps over the lazy dog.", "鸮鸮", "start", "long"),
        (placeholder(512, 512), "nickname", "start", "512x512"),
        (placeholder(200, 600), "这里是一个很长很长很长很长的昵称", "start", "200x600"),
    ]

    messages = []
    for i, (content, nickname, alignment, name) in enumerate(testcases):
        msg = MessageObject(
            MessageSegment.text(content) if
            not isinstance(content, Image.Image) else MessageSegment.image_url(
                filename=f"test_{i:05d}.png",
                url=f"https://placehold.co/{content.width}x{content.height}.png"
            ))
        alignment = Alignment.START if alignment == "start" else Alignment.END
        message = await MessageRender.create(avatar=avatar,
                                             content=msg,
                                             nickname=nickname,
                                             alignment=alignment)
        message.render().save(out / f"{name}.png")
        messages.append(
            Conversation(avatar=avatar,
                         content=msg,
                         nickname=nickname,
                         alignment=alignment))

    complex_msg = MessageObject([
        MessageSegment.text("Leading text"),
        MessageSegment.image_url(filename="test_512x512.png",
                                 url="https://placehold.co/512x512.png"),
        MessageSegment.text("Trailing text"),
        MessageSegment.at(111),
        MessageSegment.face(0),
        MessageSegment.text("end")
    ])

    message_complex = await MessageRender.create(avatar=avatar,
                                                 content=complex_msg,
                                                 nickname="complex")
    message_complex.render().save(out / "complex.png")

    messages.append(
        Conversation(avatar=avatar, content=complex_msg, nickname="complex"))

    (await MessageRender.create_conversation(messages)).render().save(
        out / "all.png")
