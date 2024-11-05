from abc import ABC, abstractmethod
from io import BytesIO
from typing import Iterable

from PIL import Image


class ImageProcessor(ABC):

    @classmethod
    def is_gif(cls, image: Image.Image) -> bool:
        return getattr(image, "is_animated", False)

    @classmethod
    def gif_iter(cls, image: Image.Image) -> Iterable[Image.Image]:
        """Iterate over the frames of a GIF image."""
        for i in range(getattr(image, "n_frames", 1)):
            image.seek(i)
            yield image.copy()

    @classmethod
    def scale(
        cls,
        image: Image.Image,
        *,
        min_size: tuple[int, int] | None = None,
        max_size: tuple[int, int] | None = None,
        resample: Image.Resampling = Image.Resampling.LANCZOS,
    ) -> Image.Image:
        """Scale an image to fit within a given size range."""
        if min_size and max_size:
            raise ValueError("min_size and max_size cannot be used together")
        if max_size:
            im = image.copy()
            im.thumbnail(max_size, resample)
            return im
        if min_size:
            width, height = image.size
            if width < min_size[0] or height < min_size[1]:
                scale = max(min_size[0] / width, min_size[1] / height)
                return image.resize((int(width * scale), int(height * scale)),
                                    resample)
        return image

    def process(self, image: Image.Image, *args,
                **kwargs) -> BytesIO | Image.Image | None:
        """Process an image."""
        if not self.is_gif(image):
            return self.process_frame(image, *args, **kwargs)
        durations, frames = [], []
        for frame in self.gif_iter(image):
            duration = frame.info["duration"]
            durations.append(duration)
            frame = self.process_frame(frame, *args, **kwargs)
            frames.append(frame)
        io = BytesIO()
        frames[0].save(io,
                       format="GIF",
                       save_all=True,
                       append_images=frames[1:],
                       duration=durations,
                       loop=0,
                       disposal=2)
        io.seek(0)
        return io

    @abstractmethod
    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        """Process a single frame of an image."""

    @classmethod
    def supports(cls, image: Image.Image) -> bool:
        """Check if an image is supported by this processor."""
        return True
