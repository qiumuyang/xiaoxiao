import cv2
import numpy as np
from PIL import Image


def generate_squircle_points(width: int = 200,
                             height: int = 100,
                             n: int = 4,
                             num_points: int = 50) -> np.ndarray:
    """Generate squircle points."""
    short, long = min(width, height), max(width, height)
    is_wider = width >= height

    if not is_wider:
        transposed = generate_squircle_points(height, width, n, num_points)
        return transposed[:, ::-1]

    a, b = short / 2, short / 2  # Use the shorter side for rounded corners
    space = short / 8  # Space between straight and curved parts
    extra = (long - short) / 2

    t = np.linspace(0, np.pi / 2, num_points, endpoint=False)
    x = a * (np.cos(t)**(2 / n))
    y = b * (np.sin(t)**(2 / n))

    if is_wider:
        right_top = np.column_stack([x + extra, y])
        top_straight = np.column_stack([
            np.linspace(a - space, -a + space, num_points // 2),
            np.full(num_points // 2, b)
        ])
        left_top = np.column_stack([-x - extra, y])[::-1]
        left_bottom = np.column_stack([-x - extra, -y])
        bottom_straight = np.column_stack([
            np.linspace(-a + space, a - space, num_points // 2),
            np.full(num_points // 2, -b)
        ])
        right_bottom = np.column_stack([x + extra, -y])[::-1]

        points = np.vstack([
            right_top, top_straight[1:], left_top, left_bottom,
            bottom_straight[1:], right_bottom
        ])
    else:
        top_right = np.column_stack([x, y + extra])
        right_straight = np.column_stack([
            np.full(num_points // 2, a),
            np.linspace(b - space, -b + space, num_points // 2)
        ])
        bottom_right = np.column_stack([x, -y - extra])[::-1]
        bottom_left = np.column_stack([-x, -y - extra])
        left_straight = np.column_stack([
            np.full(num_points // 2, -a),
            np.linspace(-b + space, b - space, num_points // 2)
        ])
        top_left = np.column_stack([-x, y + extra])[::-1]

        points = np.vstack([
            top_right, right_straight[1:], bottom_right, bottom_left,
            left_straight[1:], top_left
        ])

    points += np.array([width / 2, height / 2])
    return points.astype(np.int32)


def draw_squircle_opencv(
    width: int,
    height: int,
    fill: tuple[int, int, int, int],
    n: int = 4,
) -> np.ndarray:
    """Draw a squircle using OpenCV with an RGBA transparent fill."""
    img = np.zeros((height, width, 4), dtype=np.uint8)
    points = generate_squircle_points(width - 1, height - 1, n)

    if fill[3] > 0:
        cv2.fillPoly(img, [points], color=fill)

    return img


def draw_squircle(width: int,
                  height: int,
                  fill: tuple[int, int, int, int],
                  n: int = 3) -> Image.Image:
    if width <= 0 or height <= 0:
        # guard against invalid dimensions
        return Image.new("RGBA", (width, height), fill)
    r, g, b, a = fill
    antialias = 2
    w2, h2 = width * antialias, height * antialias
    array = draw_squircle_opencv(w2, h2, (r, g, b, a), n)
    img = Image.fromarray(array)
    return img.resize((width, height), Image.Resampling.BILINEAR)
