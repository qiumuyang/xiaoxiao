from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypedDict, TypeVar

from mistletoe.block_token import BlockToken
from typing_extensions import Unpack

from src.utils.render import RenderObject, TextStyle

if TYPE_CHECKING:
    from .render import MarkdownRenderer

T = TypeVar("T", bound=BlockToken, contravariant=True)


class ContextAttrs(TypedDict, total=False):
    style: TextStyle
    max_width: int
    indent: int
    block_spacing: int


@dataclass
class Context:
    style: TextStyle
    max_width: int
    indent: int
    block_spacing: int

    def temp(self, **kwargs: Unpack[ContextAttrs]):

        class TempContext(Context):

            def __init__(self, ctx: Context,
                         **kwargs: Unpack[ContextAttrs]) -> None:
                self.ctx = ctx
                self.original = {k: getattr(ctx, k) for k in kwargs}
                self.to_update = kwargs

            def __enter__(self) -> "TempContext":
                for k, v in self.to_update.items():
                    setattr(self.ctx, k, v)
                return self

            def __exit__(self, *args) -> None:
                for k, v in self.original.items():
                    setattr(self.ctx, k, v)

        return TempContext(self, **kwargs)


class BlockRenderer(Protocol[T]):
    """Render a block token to a render object (image)."""

    def __init__(self, master: "MarkdownRenderer") -> None:
        ...

    def render(self, token: T, ctx: Context) -> RenderObject:
        ...
