from __future__ import annotations

from typing import Iterable

from typing_extensions import Self, Unpack, override

from ...base import (Alignment, BaseStyle, Direction, RenderImage,
                     RenderObject, cached, volatile)
from ..container import Container
from .utils import split_subarray, split_subarray_unordered


class WaterfallContainer(Container):

    def __init__(
        self,
        alignment: Alignment,
        columns: int,
        children: Iterable[RenderObject],
        spacing: int,
        ordered: bool,
        **kwargs: Unpack[BaseStyle],
    ):
        super().__init__(alignment, Direction.VERTICAL, children, spacing,
                         **kwargs)
        with volatile(self):
            self.columns = columns
            self.ordered = ordered

    @classmethod
    def from_children(  # type: ignore
        cls,
        children: Iterable[RenderObject],
        columns: int,
        alignment: Alignment = Alignment.START,
        spacing: int = 0,
        ordered: bool = True,
        **kwargs: Unpack[BaseStyle],
    ) -> Self:
        return cls(alignment, columns, children, spacing, ordered, **kwargs)

    @property
    @cached
    @override
    def content_width(self) -> int:
        return self.render_content().width

    @property
    @cached
    @override
    def content_height(self) -> int:
        return self.render_content().height

    def _split_columns_ordered(self) -> list[list[RenderObject]]:
        if not self.children:
            return []
        split_points = split_subarray(
            [child.height + self.spacing for child in self.children],
            min(self.columns, len(self.children)))
        prev = 0
        columns = []
        for split in split_points:
            columns.append(self.children[prev:split])
            prev = split
        columns.append(self.children[prev:])
        if len(columns) < self.columns:
            columns += [[] for _ in range(self.columns - len(columns))]
        return columns

    def _split_columns_unordered(self) -> list[list[RenderObject]]:
        if not self.children:
            return []
        sub_indices = split_subarray_unordered(
            [child.height + self.spacing for child in self.children],
            min(self.columns, len(self.children)))
        for sub in sub_indices:
            sub.sort()
        sub_indices.sort(key=lambda lst: min(lst))
        columns = []
        for sub in sub_indices:
            columns.append([self.children[i] for i in sub])
        if len(columns) < self.columns:
            columns += [[] for _ in range(self.columns - len(columns))]
        return columns

    @cached
    def render_content(self) -> RenderImage:
        if not self.children:
            return RenderImage.empty(0, 0)

        if self.ordered:
            columns = self._split_columns_ordered()
        else:
            columns = self._split_columns_unordered()
        heights = [sum(child.height for child in column) for column in columns]
        index, max_height = max(enumerate(heights), key=lambda x: x[1])
        max_height += (len(columns[index]) - 1) * self.spacing

        rendered = []
        for column, height in zip(columns, heights):
            if not column:
                continue
            if len(column) > 1:
                spacing = (max_height - height) // (len(column) - 1)
            else:
                spacing = 0
            rendered.append(
                RenderImage.concat_vertical(
                    [child.render() for child in column],
                    alignment=self.alignment,
                    spacing=spacing))

        return RenderImage.concat_horizontal(rendered,
                                             alignment=Alignment.START,
                                             spacing=self.spacing)
