import base64
from io import BytesIO

import requests
from PIL import Image

from src.utils.render import RenderImage


def fetch_image(url: str) -> RenderImage:
    if url.startswith(("http://", "https://")):
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        image = Image.open(BytesIO(resp.content))
        return RenderImage.from_pil(image)
    if url.startswith("file://"):
        image = Image.open(url.removeprefix("file://"))
        return RenderImage.from_pil(image)
    if url.startswith("data:image/"):
        fmt, data = url.removeprefix("data:image/").split(",")
        if not fmt.endswith(";base64"):
            raise ValueError(f"Unsupported image format: {fmt}")
        image = Image.open(BytesIO(base64.b64decode(data)))
        return RenderImage.from_pil(image)
    raise ValueError(f"Unsupported image URL: {url}")
