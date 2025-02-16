from io import BytesIO
from typing import Literal

from PIL import Image

from src.utils.auto_arg import Argument
from src.utils.doc import CommandCategory, command_doc

from .processor import ImageProcessor


@command_doc("拉近", category=CommandCategory.IMAGE, visible_in_overview=False)
class Zoom(ImageProcessor):
    """
    生成**{"镜头" + cmd}**效果的动图

    Usage:
        {Zoom.format_args()}

    Examples:
        {Zoom.format_example()}
    """

    size = Argument(2.0, range=(1.25, 4), positional=True, doc="放大倍数")
    duration = Argument(2.0, range=(0.5, 5), positional=True, doc="总时长 (秒)")

    def __init__(self, mode: Literal["in", "out"]) -> None:
        super().__init__()
        self.mode = mode

    def process(self, image: Image.Image, size: float,
                duration: float) -> BytesIO:
        min_frames = 15
        duration *= 1000  # Convert to milliseconds
        default_frame_duration = int(duration / min_frames)
        if self.is_gif(image):
            frames, durations = [], []
            while len(frames) < min_frames:
                for frame in self.gif_iter(image):
                    durations.append(frame.info["duration"]
                                     or default_frame_duration)
                    frames.append(frame.convert("RGBA"))
            # rescale the duration to match the total duration
            # total_duration = sum(durations)
            # durations = [int(duration * d / total_duration) for d in durations]
        else:
            frames = [image.convert("RGBA")] * min_frames
            durations = [default_frame_duration] * min_frames

        zoom_factor = [
            1 + (size - 1) * i / (len(frames) - 1) for i in range(len(frames))
        ]
        if self.mode == "out":
            # Reverse the zoom factor to zoom out
            zoom_factor.reverse()
        for i, (frame, factor) in enumerate(zip(frames, zoom_factor)):
            width, height = frame.size
            new_w = int(width / factor)
            new_h = int(height / factor)
            left = (width - new_w) // 2
            top = (height - new_h) // 2
            cropped = frame.crop((left, top, left + new_w, top + new_h))
            frames[i] = cropped.resize((width, height),
                                       Image.Resampling.LANCZOS)

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

    def process_frame(self, image: Image.Image, *args,
                      **kwargs) -> Image.Image:
        raise NotImplementedError()


command_doc("拉远", category=CommandCategory.IMAGE,
            visible_in_overview=False)(Zoom)
