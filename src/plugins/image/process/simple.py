import math
from io import BytesIO
from typing import Literal

from PIL import Image

from .processor import ImageProcessor


class Reflect(ImageProcessor):
    """Copy half of the image and flip it to the other half."""

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


class Reverse(ImageProcessor):
    """Reverse the gif."""

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


class GrayScale(ImageProcessor):
    """Convert the image to grayscale."""

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        result = image.convert("L")
        return result


class Flip(ImageProcessor):
    """Flip the image."""

    def __init__(self, direction: Literal["horizontal", "vertical"]) -> None:
        super().__init__()
        if direction == "horizontal":
            self.method = Image.Transpose.FLIP_LEFT_RIGHT
        else:
            self.method = Image.Transpose.FLIP_TOP_BOTTOM

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        return image.transpose(self.method)
