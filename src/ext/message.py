from io import BytesIO
from pathlib import Path

import nonebot.adapters.onebot.v11 as v11
from PIL import Image
from typing_extensions import override


class MessageSegment(v11.MessageSegment):

    @classmethod
    @override
    def image(
        cls,
        image: str | bytes | BytesIO | Path | Image.Image,
        type_: str | None = None,
        cache: bool = True,
        proxy: bool = True,
        timeout: int | None = None,
    ) -> v11.MessageSegment:
        if isinstance(image, Image.Image):
            io = BytesIO()
            image.save(io, format="PNG")
            io.seek(0)
            file = io
        else:
            file = image
        return v11.MessageSegment.image(file, type_, cache, proxy, timeout)
