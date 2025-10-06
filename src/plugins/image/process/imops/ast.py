from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Ratio:
    value: float
    unit: Literal["ratio", "px"] = "ratio"


@dataclass
class LayoutCell:
    tile_id: str
    ratio: Ratio | None = None


@dataclass
class LayoutRow:
    cells: list[LayoutCell]
    ratio: Ratio | None = None


@dataclass
class Layout:
    rows: list[LayoutRow]


@dataclass
class Suffix:
    type: Literal["flip_h", "flip_v", "rotate"]
    param: float | None = None

    @classmethod
    def compress(cls, *suffixes: "Suffix") -> list["Suffix"]:
        degree = 0
        flip_h = False
        flip_v = False
        for suffix in suffixes:
            if suffix.type == "rotate":
                degree += suffix.param or 0
            elif suffix.type == "flip_h":
                flip_h = not flip_h
            elif suffix.type == "flip_v":
                flip_v = not flip_v
        result = []
        if degree % 360 != 0:
            result.append(Suffix("rotate", degree % 360))
        if flip_h:
            result.append(Suffix("flip_h"))
        if flip_v:
            result.append(Suffix("flip_v"))
        return result


@dataclass
class FuncCall:
    name: str
    args: list[Any] = field(default_factory=list)


@dataclass
class BuildCell:
    content: str | FuncCall
    suffixes: list[Suffix] = field(default_factory=list)


@dataclass
class BuildRow:
    cells: list[BuildCell]


@dataclass
class Build:
    rows: list[BuildRow]
