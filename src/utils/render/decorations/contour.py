from enum import Enum

import cv2
import numpy as np
import numpy.typing as npt
from typing_extensions import Self, override

from ..base import Color, LayerDecoration, Overlay, RenderImage, RenderObject
from ..utils import cast


class ContourType(Enum):
    EXTERNAL = cv2.RETR_EXTERNAL
    ALL = cv2.RETR_TREE


class Contour(LayerDecoration):
    """Draw a contour around the foreground of the image.

    Attributes:
        color: color of the contour
        thickness: thickness of the contour
        dilation: size of the dilation kernel
        contour_type: type of the contour, either EXTERNAL or ALL
        threshold: threshold of alpha channel for foreground
        overlay: layer relationship to the decorated image
    """

    def __init__(
        self,
        color: Color,
        thickness: int,
        dilation: int,
        contour_type: ContourType,
        threshold: int,
        overlay: Overlay,
    ) -> None:
        super().__init__(overlay)
        self.color = color
        self.thickness = thickness
        self.dilation = dilation
        self.contour_type = contour_type
        self.threshold = threshold

    @classmethod
    def of(
        cls,
        color: Color,
        thickness: int = 0,
        dilation: int = 0,
        contour_type: ContourType = ContourType.EXTERNAL,
        threshold: int = 0,
        overlay: Overlay = Overlay.ABOVE_COMPOSITE,
    ) -> Self:
        return cls(color, thickness, dilation, contour_type, threshold,
                   overlay)

    @override
    def render_layer(self, im: RenderImage, obj: RenderObject) -> RenderImage:
        alpha = cast[npt.NDArray[np.uint8]](im.base_im[:, :, 3])
        trunc_alpha = np.where(alpha > self.threshold, alpha,
                               0).astype(np.uint8)
        if self.dilation > 0:
            trunc_alpha = cv2.dilate(
                trunc_alpha, np.ones((self.dilation, self.dilation), np.uint8))

        layer = RenderImage.empty_like(im)
        contours, _ = cv2.findContours(
            trunc_alpha,
            self.contour_type.value,
            cv2.CHAIN_APPROX_NONE,
        )
        layer.base_im = cv2.drawContours(
            layer.base_im,
            contours,
            -1,
            self.color,
            self.thickness,
            cv2.LINE_AA,
        )
        # apply foreground alpha channel back to layer
        layer.base_im[:, :, 3] = np.where(
            trunc_alpha,
            255 - trunc_alpha,  # invert alpha channel # type: ignore
            layer.base_im[:, :, 3],
        )
        return layer
