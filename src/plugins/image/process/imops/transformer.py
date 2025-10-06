from lark import Transformer

from .ast import (Build, BuildCell, BuildRow, FuncCall, Layout, LayoutCell,
                  LayoutRow, Ratio, Suffix)


class ImOpsTransformer(Transformer):

    def start(self, items):
        layout, build = items
        return layout, build

    def layout(self, rows):
        return Layout(rows)

    def layout_row(self, args):
        if isinstance(args[-1], Ratio):
            vratio = args[-1]
            cells = args[:-1]
        else:
            vratio = None
            cells = args
        return LayoutRow(cells, vratio)

    def cell(self, args):
        tile = args[0]
        hratio = args[1] if len(args) > 1 else None
        return LayoutCell(tile, hratio)

    def build(self, args):
        return Build(args)

    def build_row(self, args):
        return BuildRow(args)

    def build_cell(self, args):
        # 直接传递 build_cell 内部对象
        return args[0]

    def suffix_tile(self, args):
        suffixes = []
        for s in args[1:]:
            s = str(s)
            if s == "'":
                suffixes.append(Suffix("flip_h"))
            elif s == "^":
                suffixes.append(Suffix("flip_v"))
            elif s.startswith("@"):
                suffixes.append(Suffix("rotate", float(s[1:])))
        return BuildCell(content=str(args[0]), suffixes=suffixes)

    def func_call(self, args):
        if len(args) == 1:
            func_name = str(args[0])
            func_args = []
        else:
            func_name = str(args[0])
            func_args = args[1]
        return BuildCell(content=FuncCall(func_name, func_args), suffixes=[])

    def func_args(self, args):
        return args

    def hratio(self, args):
        return args[0]

    def vratio(self, args):
        return args[0]

    def RATIO(self, token):
        return Ratio(float(token), "ratio")

    def PIXEL(self, token):
        return Ratio(float(token[:-2]), "px")

    def NUMBER(self, token):
        return float(token)

    def TILE(self, token):
        return str(token)

    def SUFFIX(self, token):
        return str(token)

    def FUNC_NAME(self, token):
        return str(token)
