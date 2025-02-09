import mistletoe
from mistletoe.ast_renderer import AstRenderer
from mistletoe.block_token import BlockToken
from mistletoe.token import Token

from src.utils.render import RenderObject, Spacer

from .math import BlockMath, InlineMath
from .proto import BlockRenderer, Context
from .style import MarkdownStyle


class MarkdownRenderer:
    """
    Converting mistletoe-parsed Markdown tokens into RenderObject.
    """

    _factory: dict[type[Token], type[BlockRenderer]] = {}

    @classmethod
    def register(cls, token_type: type[Token]):

        def decorator(func: type[BlockRenderer]):
            cls._factory[token_type] = func
            return func

        return decorator

    def __init__(self,
                 text: str,
                 style: MarkdownStyle = MarkdownStyle(),
                 content_width: int = 800) -> None:
        self.text = text
        self.style = style
        self.content_width = content_width
        with AstRenderer(InlineMath, BlockMath):
            self.doc = mistletoe.Document(text)

    def render(self) -> RenderObject:
        return self._dispatch_render(self.doc,
                                     ctx=Context(
                                         style=self.style.main,
                                         max_width=self.content_width,
                                         indent=0,
                                         block_spacing=self.style.spacing))

    def _dispatch_render(
        self,
        token: BlockToken,
        ctx: Context,
    ) -> RenderObject:
        renderer = self._factory.get(token.__class__)
        if not renderer:
            print("Not implemented", token.__class__.__name__)
            return Spacer.of()
        return renderer(self).render(token, ctx)
