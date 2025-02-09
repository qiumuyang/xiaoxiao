import io

import matplotlib.pyplot as plt
from PIL import Image


def render_equation(equation: str,
                    font_size: float,
                    *,
                    dpi: int = 100,
                    color: str = "#000000") -> Image.Image:
    """
    Render LaTeX text with dynamically adjusted figure size.
    """
    # Create a temporary figure to measure text size
    fig, ax = plt.subplots()
    ax.axis("off")
    text_obj = ax.text(0.5,
                       0.5,
                       equation,
                       fontsize=font_size,
                       ha="center",
                       va="center")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()  # type: ignore
    bbox = text_obj.get_window_extent(renderer=renderer)
    plt.close(fig)

    # Compute dynamic figsize based on text size
    width_inches = bbox.width / dpi + 0.5  # Add some padding
    height_inches = bbox.height / dpi + 0.2

    # Create new figure with adjusted size
    fig, ax = plt.subplots(figsize=(width_inches, height_inches), dpi=dpi)
    ax.axis("off")
    ax.text(0.5, 0.5, equation, fontsize=font_size, ha="center", va="center")
    ax.patch.set_facecolor(color)
    fig.canvas.draw()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    buf.seek(0)
    image = Image.open(buf)
    plt.close(fig)
    return image
