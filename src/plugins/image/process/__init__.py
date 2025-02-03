from .flip_flop import FlipFlop
from .processor import ImageProcessor
from .rotate import MultiRotate
from .shake import Shake
from .should_i_always import ShouldIAlways
from .simple import Flip, GrayScale, Reflect, Reverse
from .xl import FourColorGrid

__all__ = [
    "Flip",
    "FlipFlop",
    "FourColorGrid",
    "GrayScale",
    "ImageProcessor",
    "Reflect",
    "Reverse",
    "MultiRotate",
    "Shake",
    "ShouldIAlways",
]
