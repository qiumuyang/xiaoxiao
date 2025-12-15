import argparse
from pathlib import Path

from lark import Lark, exceptions
from PIL import Image, ImageOps

from src.utils.auto_arg import Argument
from src.utils.doc import CommandCategory, command_doc

from ..processor import ImageProcessor
from . import ast
from .exception import DSLParseError
from .transformer import ImOpsTransformer
from .utils import calculate_real_size

grammar = (Path(__file__).parent / "grammar.lark").read_text(encoding="utf-8")
parser = Lark(grammar, start="start", parser="lalr")
transformer = ImOpsTransformer()


class ConcatArgParser:

    def __init__(self, dest: str, joiner: str = " ") -> None:
        self.dest = dest
        self.joiner = joiner

    def parse_args(self, args=None, namespace=None) -> argparse.Namespace:
        result = argparse.Namespace()
        setattr(result, self.dest, self.joiner.join(args) if args else "")
        return result


@command_doc("tile", category=CommandCategory.IMAGE, visible_in_overview=False)
class TileScript(ImageProcessor):
    """
    基于语法的图片切割与拼接

    ### 语法定义

    ```
    <layout> -> <build>
    ```

    | 组成部分 | 格式 | 说明 | 示例 |
    |---|---|---|---|
    | ID | 大写字母或下划线 | 定义(layout)或引用(build)图片块 | `A`, `B`, `LEFT`, `_` |
    | **layout 阶段** | | | |
    | 块切割比例 | 数字或像素值，跟随ID | 定义块在行内比例，默认为`1` | `A2`, `B100px`|
    | 块分隔符 | `\\|` | | `A\\|B\\|C`, `L\\|_10px\\|R` |
    | 行切割比例 | 块切割比例加`<>`，跟随行末ID | 定义行占总高度比例，默认为`1` | |
    | 行分隔符 | `;` | | `A\\|B<3>;C\\|D<1>` |
    | **build 阶段** | | | |
    | 水平翻转 | `'` |  | `A'` |
    | 垂直翻转 | `^` |  | `B^` |
    | 旋转 | `@<数字>` | 顺时针旋转 | `C@90` |

    | 示例 | 说明 |
    |---|---|
    | `A\\|B -> A\\|A'` | 水平切割等宽两块，将左块翻转后粘贴到右块 (即**憋不不憋**) |
    | `A;_<100px> -> A` | 移除图片底部100px |
    | `A\\|B2;C\\|D2<2> -> D\\|B@90\\|C@90\\|A` | |

    """

    expr = Argument("", positional=True, doc="操作定义")

    def __init__(self) -> None:
        super().__init__()
        self._parser = ConcatArgParser("expr")

    def process_frame(self, image: Image.Image, expr: str) -> Image.Image:
        try:
            tree = parser.parse(expr)
        except exceptions.UnexpectedInput as e:
            raise DSLParseError(str(e),
                                line=e.line,
                                column=e.column,
                                text=expr) from e
        except exceptions.LarkError as e:
            # 其他 Lark 异常
            raise DSLParseError(str(e)) from e
        layout, build = transformer.transform(tree)
        tiles = split(layout, image)
        image = merge(build, tiles, image.mode)
        return image


def split(layout: ast.Layout, image: Image.Image) -> dict[str, Image.Image]:
    w, h = image.size
    tiles: dict[str, Image.Image] = {}
    heights = calculate_real_size(h, *[row.ratio for row in layout.rows])
    y = 0
    for i, row in enumerate(layout.rows):
        x = 0
        widths = calculate_real_size(w, *[cell.ratio for cell in row.cells])
        for j, cell in enumerate(row.cells):
            tile_id = cell.tile_id
            tile = image.crop((x, y, x + widths[j], y + heights[i]))
            tiles[tile_id] = tile
            x += widths[j]
        y += heights[i]
    return tiles


def merge(
    build: ast.Build,
    tiles: dict[str, Image.Image],
    mode: str,
) -> Image.Image:
    mat: list[list[Image.Image]] = []
    for row in build.rows:
        mat_row: list[Image.Image] = []
        for cell in row.cells:
            mat_row.append(build_cell(cell, tiles))
        mat.append(mat_row)
    h = sum(row[0].height for row in mat)
    w = sum(img.width for img in mat[0])
    canvas = Image.new(mode, (w, h))
    y = 0
    for row in mat:
        x = 0
        for img in row:
            if img.mode in ("RGBA", "LA") or (img.mode == "P"
                                              and "transparency" in img.info):
                canvas.alpha_composite(img, (x, y))
            else:
                canvas.paste(img, (x, y))
            x += img.width
        y += row[0].height
    return canvas


def build_cell(
    cell: ast.BuildCell,
    tiles: dict[str, Image.Image],
) -> Image.Image:
    # 1. get tile
    if isinstance(cell.content, str):
        if cell.content not in tiles:
            raise ValueError(f"'{cell.content}' not defined")
        img = tiles[cell.content]
    else:
        img = build_func_call(cell.content, tiles)
    # 2. apply suffixes
    suffixes = ast.Suffix.compress(*cell.suffixes)
    for suffix in suffixes:
        if suffix.type == "rotate" and suffix.param:
            img = img.rotate(-suffix.param,
                             expand=True,
                             resample=Image.Resampling.LANCZOS)
        elif suffix.type == "flip_h":
            img = ImageOps.mirror(img)
        elif suffix.type == "flip_v":
            img = ImageOps.flip(img)
    if not suffixes:
        # the above operations always make a copy
        # if no operation is applied, make a copy here
        img = img.copy()
    return img


def build_func_call(
    func_call: ast.FuncCall,
    tiles: dict[str, Image.Image],
) -> Image.Image:
    raise NotImplementedError
