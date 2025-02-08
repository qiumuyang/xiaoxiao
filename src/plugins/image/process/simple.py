import math
from io import BytesIO
from typing import Literal

from PIL import Image

from src.utils.doc import CommandCategory, command_doc

from .processor import ImageProcessor


@command_doc("憋不不憋",
             aliases={"向右反射"},
             category=CommandCategory.IMAGE,
             visible_in_overview=False)
class Reflect(ImageProcessor):
    """
    将图片的一半复制并翻转到另一半

    Special:
        憋不住了 => 憋不不憋
    """

    CROP = {
        "L": (0, 0, 0.5, 1),
        "R": (0.5, 0, 1, 1),
        "T": (0, 0, 1, 0.5),
        "B": (0, 0.5, 1, 1),
    }
    TRANS: dict[str, Image.Transpose] = {
        "L": Image.Transpose.FLIP_LEFT_RIGHT,
        "R": Image.Transpose.FLIP_LEFT_RIGHT,
        "T": Image.Transpose.FLIP_TOP_BOTTOM,
        "B": Image.Transpose.FLIP_TOP_BOTTOM,
    }

    def __init__(self, direction: Literal["L2R", "R2L", "T2B", "B2T"]) -> None:
        super().__init__()
        self.source = direction[0]

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        w, h = image.size
        l, t, r, b = self.CROP[self.source]
        lx, ty, rx, by = map(math.floor, (w * l, h * t, w * r, h * b))
        half = image.crop((lx, ty, rx, by))
        half = half.transpose(self.TRANS[self.source])
        result = image.copy()
        result.paste(half, (math.ceil(w * (1 - r)), math.ceil(h * (1 - b))))
        return result


command_doc("向左反射", category=CommandCategory.IMAGE,
            visible_in_overview=False)(Reflect)
command_doc("向上反射", category=CommandCategory.IMAGE,
            visible_in_overview=False)(Reflect)
command_doc("向下反射", category=CommandCategory.IMAGE,
            visible_in_overview=False)(Reflect)


@command_doc("倒放", category=CommandCategory.IMAGE, visible_in_overview=False)
class Reverse(ImageProcessor):
    """
    将动图**倒放**

    Special:
        激活时间轴逆向解析协议…脑啡肽正在回溯帧时间戳……重构完成度98.7%。

    Note:
        - 仅限动图 (GIF)
    """

    @classmethod
    def supports(cls, image: Image.Image) -> bool:
        return cls.is_gif(image)

    def process(self, image: Image.Image, *args, **kwargs) -> BytesIO:
        frames = list(self.gif_iter(image))
        frames.reverse()
        durations = [f.info["duration"] for f in frames]
        io = BytesIO()
        frames[0].save(io,
                       format="GIF",
                       save_all=True,
                       append_images=frames[1:],
                       loop=0,
                       duration=durations,
                       disposal=2)
        return io

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        return image


@command_doc("灰度", category=CommandCategory.IMAGE, visible_in_overview=False)
class GrayScale(ImageProcessor):
    """
    将图片转换为**灰度**图

    Special:
        启动单色光谱解析协议//正在抑制RGB通道

        ……建议切换至医疗部门色觉诊断模式。
    """

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        result = image.convert("L")
        return result


@command_doc("翻转", category=CommandCategory.IMAGE, visible_in_overview=False)
class Flip(ImageProcessor):
    """
    将图片**{"水平" if cmd == "镜像" else "垂直"}**翻转

    Special:
        加载镜面反射协议//调用莱茵生命光学实验记录B-14。
    """

    def __init__(self, direction: Literal["horizontal", "vertical"]) -> None:
        super().__init__()
        if direction == "horizontal":
            self.method = Image.Transpose.FLIP_LEFT_RIGHT
        else:
            self.method = Image.Transpose.FLIP_TOP_BOTTOM

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        return image.transpose(self.method)


command_doc("镜像", category=CommandCategory.IMAGE,
            visible_in_overview=False)(Flip)
