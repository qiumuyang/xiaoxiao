from argparse import ArgumentParser
from io import BytesIO
from typing import Literal

from PIL import Image

from .processor import ImageProcessor


class FlipFlop(ImageProcessor):
    """Flip the image back and forth to create a GIF."""

    TRANS = {
        "horizontal": Image.Transpose.FLIP_LEFT_RIGHT,
        "vertical": Image.Transpose.FLIP_TOP_BOTTOM,
    }

    def __init__(
        self,
        direction: Literal["horizontal", "vertical"],
        flip_per_sec: int = 6,
    ) -> None:
        self.direction = direction
        self.flip_per_sec = flip_per_sec

        parser = ArgumentParser()
        parser.add_argument("flip_per_sec", type=float, nargs="?")
        parser.add_argument("--fps", type=float, required=False)
        self.parser = parser

    def process(self, image: Image.Image, *args, **kwargs) -> BytesIO:
        try:
            args = self.parser.parse_args(args[1:])
            fps = args.flip_per_sec or args.fps or self.flip_per_sec
        except KeyboardInterrupt:
            raise
        except:
            fps = self.flip_per_sec
        fps = min(max(0.5, fps), 40)
        state_duration = round(1000 / fps)
        if self.is_gif(image):
            durations, frames = [], []
            current_duration = 0
            current_state = 0
            flips = 0
            while 1:
                for frame in self.gif_iter(image):
                    # in some cases, the duration is 0,
                    # which causes the loop to run forever
                    duration = frame.info["duration"] or 100
                    durations.append(duration)
                    if current_duration >= state_duration:
                        current_state = 1 - current_state
                        current_duration -= state_duration
                        flips += 1
                    if current_state:
                        frame = frame.transpose(self.TRANS[self.direction])
                    current_duration += duration
                    frames.append(frame)
                if flips >= 2:
                    break
        else:
            # 2 frames: original and flipped
            has_flipped = image.transpose(self.TRANS[self.direction])
            frames = [image, has_flipped]
            durations = state_duration
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
        raise NotImplementedError
