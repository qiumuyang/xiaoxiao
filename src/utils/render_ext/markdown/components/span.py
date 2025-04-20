from mistletoe.span_token import Image, LineBreak, RawText, SpanToken
from mistletoe.token import Token

from ..render import MarkdownRenderer
from ..token import Math
from .utils.builder import Builder
from .utils.image import fetch_image
from .utils.math import render_math


class SpanRenderer:
    """Render a span token to a builder.

    Builder can be used to build render objects."""

    @classmethod
    def render(cls, master: MarkdownRenderer, token: Token,
               builder: Builder) -> Builder:
        for span in token.children or []:
            if not isinstance(span, SpanToken):
                raise ValueError(f"Unexpected non-span token: {span}")
            match span:
                case RawText():
                    builder.text(span.content.replace("<br>", "\n"))
                case LineBreak():
                    if not span.soft:
                        builder.text("\n")
                case Math():
                    try:
                        builder.image(render_math(span.math,
                                                  span.inline,
                                                  max_width=builder.max_width),
                                      tag="eq_",
                                      inline=span.inline)
                    except Exception:
                        builder.text("[公式渲染错误]")
                case Image():
                    try:
                        builder.image(fetch_image(span.src),
                                      caption=(span.title,
                                               master.style.caption))
                    except Exception:
                        alt_text = "图片渲染错误"
                        if span.children:
                            obj = next(iter(span.children))
                            if isinstance(obj, RawText):
                                alt_text = obj.content
                        builder.text(f"[{alt_text}]")
                case _:
                    style_with_name = master.style.span.get(type(span))
                    if not style_with_name:
                        raise NotImplementedError(
                            f"Unsupported span token: {span}")
                    style, name = style_with_name
                    with builder.style(name, style, dedup=False):
                        cls.render(master, span, builder)
        return builder
