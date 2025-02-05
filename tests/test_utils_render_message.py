from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from src.utils.render_ext.message import Message


def placeholder(width: int, height: int) -> Image.Image:
    r = requests.get(f"https://placehold.co/{width}x{height}.png")
    r.raise_for_status()
    return Image.open(BytesIO(r.content))


def test_render_message():
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

    for content, nickname, alignment, name in testcases:
        message = Message(avatar=avatar,
                          content=content,
                          nickname=nickname,
                          alignment=alignment)
        message.create().render().save(out / f"{name}.png")
