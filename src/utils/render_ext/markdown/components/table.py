from typing import Generic, Iterable, TypeVar, cast

from mistletoe.block_token import Table, TableCell, TableRow

from src.utils.render import (Alignment, Color, Container, Direction, Image,
                              Interpolation, RenderObject, Space, Spacer,
                              TextStyle)
from src.utils.render.base.image import RenderImage

from ..proto import Context
from ..render import MarkdownRenderer
from .span import SpanRenderer
from .utils.builder import Box, Builder

T = TypeVar("T")


class Mat(Generic[T]):

    def __init__(self, mat: list[list[T | None]]) -> None:
        self.mat = mat

    @property
    def num_rows(self) -> int:
        return len(self.mat)

    @property
    def num_cols(self) -> int:
        return len(self.mat[0])

    def iter_rows(self) -> Iterable[list[T | None]]:
        for row in self.mat:
            yield row

    def iter_cols(self) -> Iterable[list[T | None]]:
        for j in range(self.num_cols):
            yield [self.mat[i][j] for i in range(self.num_rows)]

    def iter_nonempty_rows(self) -> Iterable[list[T]]:
        for row in self.iter_rows():
            yield [cell for cell in row if cell]

    def iter_nonempty_cols(self) -> Iterable[list[T]]:
        for col in self.iter_cols():
            yield [cell for cell in col if cell]


@MarkdownRenderer.register(Table)
class TableRenderer:

    def __init__(self, master: MarkdownRenderer) -> None:
        self.master = master

    @classmethod
    def normalize_column_width(cls,
                               raw: list[int],
                               max_width: int,
                               *,
                               min_col_width: int,
                               thresh: float = 0.7) -> list[int]:
        """Adjust column widths to fit within max_width.

        Args:
            raw: Original column widths.
            max_width: Maximum total width.
            thresh: Threshold for extreme differences.
        """
        num_cols = len(raw)
        total = sum(raw)

        if total <= max_width:
            return raw

        if min_col_width * num_cols > max_width:
            raise ValueError("Table too wide to fit in max_width")

        scale_factor = max_width / total
        scaled = [int(w * scale_factor) for w in raw]
        # in case of rounding errors
        while sum(scaled) > max_width:
            max_idx = max(range(num_cols), key=lambda i: scaled[i])
            scaled[max_idx] -= 1

        # avoid extreme differences or too small columns
        max_w, min_w = max(scaled), min(scaled)
        thresh_abs = int(thresh * max_width)
        while max_w - min_w > thresh_abs or min(scaled) < min_col_width:
            max_idx = max(range(num_cols), key=lambda i: scaled[i])
            min_idx = min(range(num_cols), key=lambda i: scaled[i])
            scaled[max_idx] -= 1
            scaled[min_idx] += 1
            max_w, min_w = max(scaled), min(scaled)
        return scaled

    def _preprocess(self, token: Table, style: TextStyle) -> Mat[Builder]:
        rows: list[TableRow] = [token.header]
        rows.extend(cast(list[TableRow], list(token.children or [])))
        num_cols = max(len(list(row.children or [])) for row in rows)
        mat: list[list[Builder | None]] = [[None for _ in range(num_cols)]
                                           for _ in range(len(rows))]
        for i in range(len(rows)):
            cells = cast(list[TableCell], list(rows[i].children or []))
            if i == 0:  # header
                style_cell = self.master.style.table.header
                style_name = "th-{j}"
            else:
                style_cell = style
                style_name = "td-{j}"
            for j in range(len(cells)):
                builder = Builder(default=style)
                with builder.style(style_name.format(j=j), style_cell):
                    SpanRenderer.render(self.master, cells[j], builder)
                mat[i][j] = builder
        return Mat(mat)

    def _render_table(self, cells: Mat[RenderObject]):
        row_heights = [
            max(cell.height for cell in row)
            for row in cells.iter_nonempty_rows()
        ]
        col_widths = [
            max(cell.width for cell in col)
            for col in cells.iter_nonempty_cols()
        ]
        border_width = self.master.style.table.border_thick
        rendered_rows = []
        for i, row in enumerate(cells.iter_nonempty_rows()):
            if i == 0:
                align_h = Alignment.CENTER
            else:
                align_h = Alignment.START
            rendered_row = Container.from_children(
                [
                    # add extra padding for right border
                    Box(
                        cell,
                        col_widths[j],
                        row_heights[i],
                        alignment_horizontal=align_h,
                    ).build(padding=Space.of(
                        0, border_width if j == len(row) - 1 else 0, 0, 0))
                    for j, cell in enumerate(row)
                ],
                direction=Direction.HORIZONTAL,
                background=self.master.style.table.background(i),
                padding=Space.of(0, 0, 0,
                                 self.master.style.table.border_thick),
            )
            rendered_rows.append(rendered_row)
        return Container.from_children(rendered_rows,
                                       direction=Direction.VERTICAL)

    def _draw_border(self, tbl: Container,
                     cells: Mat[RenderObject]) -> RenderImage:
        image = tbl.render()
        border_width = self.master.style.table.border_thick
        border_color = Color.from_hex(self.master.style.table.border_color)
        x, y = 0, 0
        row_heights = [
            max(cell.height for cell in row)
            for row in cells.iter_nonempty_rows()
        ]
        col_widths = [
            max(cell.width for cell in col)
            for col in cells.iter_nonempty_cols()
        ]
        # decrease by border width to avoid overflow
        row_heights[-1] -= border_width
        col_widths[-1] -= border_width
        for i in range(cells.num_cols + 1):
            image.line((x, 0), (x, image.height), border_color, border_width)
            if i < cells.num_cols:
                x += col_widths[i]
        for i in range(cells.num_rows + 1):
            image.line((0, y), (image.width, y), border_color, border_width)
            if i < cells.num_rows:
                y += row_heights[i] + border_width
        return image

    def render(self, token: Table, ctx: Context) -> RenderObject:
        # 1. estimate column widths
        mat = self._preprocess(token, ctx.style)
        padding = [
            round(_ * self.master.style.unit)
            for _ in self.master.style.table.padding_factor
        ]
        # padding on both sides
        reserved_padding = mat.num_cols * 2 * padding[0]
        reserved_border = self.master.style.table.border_thick  # right border
        actual_max_width = ctx.max_width - reserved_padding - reserved_border
        raw_column_widths = [
            max(cell.build().width for cell in col)
            for col in mat.iter_nonempty_cols()
        ]
        min_column_width = (self.master.style.unit *
                            self.master.style.table.min_column_chars)
        while True:
            try:
                col_widths = self.normalize_column_width(
                    raw_column_widths,
                    actual_max_width,
                    min_col_width=min_column_width)
            except ValueError:
                # unable to fit in max_width
                # increase width then resize at the end
                actual_max_width = round(actual_max_width * 1.25)
            else:
                break
        # 2. render each cell and calculate row heights / column widths
        cells = Mat([[
            cell.build(max_width=col_widths[j],
                       padding=Space.of_side(*padding),
                       spacing=self.master.style.line_spacing)
            if cell else Spacer.of() for j, cell in enumerate(row)
        ] for row in mat.iter_rows()])
        # 3. render table
        table = self._render_table(cells)
        # 4. add border
        image = self._draw_border(table, cells)
        return Image.from_image(image).thumbnail(
            ctx.max_width, -1, interpolation=Interpolation.LANCZOS)
