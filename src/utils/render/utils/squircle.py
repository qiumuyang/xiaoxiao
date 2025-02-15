import cv2
import numpy as np
from PIL import Image


def generate_squircle_points(width: int,
                             height: int,
                             radius: float,
                             num_points: int = 200) -> np.ndarray:
    """
    Generate points for a squircle (a superellipse) whose corner curvature (at 45°)
    is set so that the offset from the inscribed square’s corner equals the fixed
    value 'corner_radius', regardless of the overall width.

    The idea is to always anchor the curvature to the short side. For a rectangle
    where width >= height, we define:
      - a = half of the short side (i.e. a = height/2)
      - extra = (width - height)/2, so the shape is centered horizontally.

    In a perfect rounded square, the superellipse parametric equations are:
         x = cx + a * sign(cos t) * |cos t|^(2/n)
         y = cy + a * sign(sin t) * |sin t|^(2/n)
    and at t = π/4 we require that
         a - (a * (√2/2)^(2/n)) = corner_radius.
    Solving for n gives:
         n = -ln2 / ln(1 - corner_radius/a)
    (with the caveat that if corner_radius <= 0 we simply use a very high n).

    If width < height we swap (and then transpose the resulting points).

    :param width: Overall width of the drawing area.
    :param height: Overall height of the drawing area.
    :param corner_radius: Fixed desired corner radius in pixels.
    :param num_points: Number of points along the full curve.
    :return: An (N, 2) array of int32 points.
    """
    # For consistent treatment, assume width is the larger dimension.
    is_wider = width >= height
    if not is_wider:
        pts = generate_squircle_points(height, width, radius, num_points)
        return pts[:, ::-1]  # swap x and y back

    if radius < 1:
        # relative
        corner_radius = radius * height
    else:
        # absolute
        corner_radius = radius
    # Use the height as the base dimension.
    a = height / 2.0  # half of the short side
    # Clamp corner_radius to be at most nearly a.
    r = min(corner_radius, a * 0.99)
    if r <= 0:
        n = 100.0  # almost a rectangle if no rounding is desired
    else:
        # At t = π/4, we want: a - a*(√2/2)^(2/n) = r.
        # That is: (√2/2)^(2/n) = 1 - (r/a)
        # Taking logarithms:
        #   2/n * ln(√2/2) = ln(1 - r/a)
        #   n = -ln2 / ln(1 - r/a)
        n = -np.log(2) / np.log(1 - (r / a))

    # Horizontal offset so that the squircle is centered in the wider image.
    cx = width / 2.0
    cy = height / 2.0
    diff = (width - height) / 2.0

    t = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
    # Compute the superellipse for a square of side 'height'
    x = a * np.sign(np.cos(t)) * (np.abs(np.cos(t)))**(2 / n)
    y = a * np.sign(np.sin(t)) * (np.abs(np.sin(t)))**(2 / n)

    # Move the negative part of the x-axis to the left side.
    # Move the positive part of the x-axis to the right side.
    x[x < 0] -= diff
    x[x >= 0] += diff

    x += cx
    y += cy

    points = np.column_stack((x, y)).astype(np.int32)
    return points


def draw_squircle_opencv(
    width: int,
    height: int,
    fill: tuple[int, int, int, int],
    radius: float,
) -> np.ndarray:
    """Draw a squircle using OpenCV with an RGBA transparent fill."""
    img = np.zeros((height, width, 4), dtype=np.uint8)
    points = generate_squircle_points(width - 1, height - 1, radius)

    if fill[3] > 0:
        cv2.fillPoly(img, [points], color=fill)

    return img


def draw_squircle(width: int,
                  height: int,
                  fill: tuple[int, int, int, int],
                  radius: float = 0.08) -> Image.Image:
    if width <= 0 or height <= 0:
        # guard against invalid dimensions
        return Image.new("RGBA", (width, height), fill)
    r, g, b, a = fill
    antialias = 2
    if antialias > 1:
        w2, h2 = width * antialias, height * antialias
        array = draw_squircle_opencv(w2, h2, (r, g, b, a), radius)
        img = Image.fromarray(array)
        return img.resize((width, height), Image.Resampling.BILINEAR)
    return Image.fromarray(
        draw_squircle_opencv(width, height, (r, g, b, a), radius))
