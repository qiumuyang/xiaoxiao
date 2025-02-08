from mistletoe.span_token import Image, LineBreak, Link, RawText, SpanToken
from mistletoe.token import Token

from ..render import MarkdownRenderer
from .builder import Builder


class SpanRenderer:
    """Render a span token to a builder.

    Builder can be used to build render objects."""

    @classmethod
    def render(cls, master: MarkdownRenderer, token: Token,
               builder: Builder) -> Builder:
        span_style = master.style.span
        for span in token.children or []:
            if not isinstance(span, SpanToken):
                raise ValueError(f"Unexpected non-span token: {span}")
            match span:
                case RawText():
                    builder.text(span.content.replace("<br>", "\n"))
                case LineBreak():
                    builder.text("\n")
                case Image():
                    # TODO: Add image support
                    with builder.style("img", span_style[Link][0]):
                        builder.text(f"[Image:{span.src}]")
                case _:
                    style_with_name = master.style.span.get(type(span))
                    if not style_with_name:
                        raise NotImplementedError(
                            f"Unsupported span token: {span}")
                    style, name = style_with_name
                    with builder.style(name, style, dedup=False):
                        cls.render(master, span, builder)
        return builder
