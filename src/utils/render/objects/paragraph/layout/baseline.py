from typing import Literal, Protocol, runtime_checkable

from ....base import RenderImage
from .element import Element


@runtime_checkable
class SupportsBaseline(Protocol):

    @property
    def baseline(self) -> int:
        ...


def concat_elements_by_baseline(
    elements: list[Element],
    mode: Literal["bottom_as_baseline", "align_bottom"] = "align_bottom",
) -> RenderImage:
    """
    Concatenates a list of elements by their baselines.

    Args:
        elements (list[Element]):
            The elements to be concatenated.
        mode (Literal["bottom_as_baseline", "align_bottom"]):
            How to align non-baseline elements.
            - "bottom_as_baseline": consider the bottom as baseline.
            - "align_bottom": bottom align with elements having baseline.

    Returns:
        RenderImage: The image of the concatenated elements.
    """
    max_below = 0
    if mode == "align_bottom":
        baseline_elements = [
            e for e in elements if isinstance(e, SupportsBaseline)
        ]
        if baseline_elements:
            max_below = max(e.height - e.baseline for e in baseline_elements)

    baselines = [
        e.baseline if isinstance(e, SupportsBaseline) else e.height - max_below
        for e in elements
    ]
    max_baseline = max(baselines)

    # (vertical start, total height)
    placements = [(max_baseline - b, e.height)
                  for (b, e) in zip(baselines, elements)]

    total_height = max(y + h for y, h in placements)
    total_width = sum(e.width for e in elements)

    canvas = RenderImage.empty(total_width, total_height)
    x_offset = 0
    for (y, _), e in zip(placements, elements):
        canvas.replace(x_offset, y, e.render())
        x_offset += e.width
    return canvas
