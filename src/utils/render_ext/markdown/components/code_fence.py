from typing import cast

from mistletoe.block_token import CodeFence
from mistletoe.span_token import RawText

from src.utils.render import (Alignment, Color, Image, RenderObject, Space,
                              Stack)
from src.utils.render.utils.squircle import draw_squircle

from ..proto import Context
from ..render import MarkdownRenderer
from .builder import Box, Builder
from .span import SpanRenderer
from .syntax_highlight import tokenize_code


@MarkdownRenderer.register(CodeFence)
class CodeFenceRenderer:

    def __init__(self, master: MarkdownRenderer) -> None:
        self.master = master

    def render(self, token: CodeFence, ctx: Context) -> RenderObject:
        main_style = self.master.style
        code_style = main_style.code_block
        children = list(token.children or [])
        if len(children) != 1 or not isinstance(children[0], RawText):
            raise ValueError(
                "CodeFence must have exactly one child of type RawText")
        code = cast(RawText, children[0]).content
        lang = token.language
        padding = [
            round(_ * main_style.unit) for _ in code_style.padding_factor
        ]
        builder = Builder(default=ctx.style, no_override=True)
        with builder.style("code-block", code_style.style):
            # builder = SpanRenderer.render(self.master, token, builder)
            for content, token_type, style_dict in tokenize_code(
                    lang, code, code_style.highlight_style):
                with builder.style(token_type, style_dict.style):
                    builder.text(content)
        content = builder.build(max_width=ctx.max_width - padding[0] * 2,
                                spacing=main_style.line_spacing,
                                padding=Space.of_side(*padding))
        squircle = Image.from_image(
            draw_squircle(ctx.max_width,
                          content.height,
                          fill=Color.from_hex(code_style.background),
                          n=6))
        # return Box(
        #     content,
        #     width=ctx.max_width,
        #     alignment_horizontal=Alignment.START,
        # ).build(background=Color.from_hex(code_style.background))
        return Stack.from_children(
            [squircle, content],
            horizontal_alignment=Alignment.START,
            vertical_alignment=Alignment.CENTER,
        )
