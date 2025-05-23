from pathlib import Path

from PIL import Image

from src.utils.doc import DocManager
from src.utils.render_ext.markdown import Markdown

cache = Path("data/dynamic/doc-markdown")


def load_document_image(name: str | None = None,
                        cached: bool = True) -> Image.Image | None:
    cache.mkdir(parents=True, exist_ok=True)
    if name is None:
        file = cache / "overview.png"
    else:
        file = cache / f"{name}.png"
    if file.exists() and cached:
        try:
            return Image.open(file)
        except:
            pass
    if name is None:
        markdown = DocManager.export_overview()
    else:
        meta = DocManager.get(name)
        if meta is None:
            return None
        markdown = meta.export_markdown()
    renderer = Markdown(markdown)
    image = renderer.render().to_pil()
    image.save(file)
    return image


def init_cache(*names: str):
    load_document_image(cached=False)
    for doc in DocManager.iter_doc():
        name_and_alias = [doc.name] + list(doc.aliases)
        if names and all(n not in name_and_alias for n in names):
            continue
        for name in name_and_alias:
            load_document_image(name, cached=False)
