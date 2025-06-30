"""Idiom data from https://github.com/pwxcoo/chinese-xinhua"""

import random
import re
from collections import Counter
from enum import Enum
from itertools import product
from pathlib import Path
from typing import Hashable, Sequence, TypedDict, TypeVar

import orjson
from pypinyin import Style as PinyinStyle
from pypinyin import lazy_pinyin, load_phrases_dict


class IdiomItem(TypedDict):
    word: str
    pinyin: list[str]
    pinyin_tone: list[str]
    explanation: str
    example: str
    derivation: str


T = TypeVar("T", bound=Hashable)


class Diff(Enum):
    """Enum for diff result.

    MISS: provided item not in target.
    EXACT: provided item matches target (position and value).
    EXIST: provided item exists in target (value only).
    """
    MISS = 0
    EXACT = 1
    EXIST = 2


class Idiom:

    idiom_table: dict[str, IdiomItem] = {}
    syllables: set[str] = set()

    @classmethod
    def init(cls):
        root = Path("data/static/chinese")
        # ==== fix pinyin ====
        fix_dict = {}
        removes = set()
        for line in (root / "fix_pinyin.txt").read_text().splitlines():
            word, *syllables = line.strip().split(" ")
            if not syllables:
                removes.add(word)
                continue
            fix_dict[word] = [[s] for s in syllables]
        load_phrases_dict(fix_dict)

        # ==== load idioms ====
        for item in orjson.loads((root / "idiom.json").read_bytes()):
            if item["word"] in removes:
                continue
            cls.idiom_table[item["word"]] = IdiomItem(
                word=item["word"],
                pinyin=lazy_pinyin(item["word"], style=PinyinStyle.NORMAL),
                pinyin_tone=lazy_pinyin(item["word"], style=PinyinStyle.TONE),
                explanation=item["explanation"].replace("”", ""),
                example=item["example"].replace("”", ""),
                derivation=item["derivation"].replace("”",
                                                      "").replace("无", ""),
            )

        # ==== load syllables ====
        for line in (root / "syllables.txt").read_text().splitlines():
            if s := line.strip():
                cls.syllables.add(s)

    @classmethod
    def random4(cls, excludes: set[str] = set()) -> IdiomItem:
        candidates = list(
            filter(lambda x: len(x) == 4 and x not in excludes,
                   cls.idiom_table))
        return cls.idiom_table[random.choice(candidates)]

    @classmethod
    def get_pinyin(cls, word: str, tone: bool = False) -> list[str]:
        return cls.idiom_table[word]["pinyin" if not tone else "pinyin_tone"]

    @classmethod
    def is_idiom(cls, word: str) -> bool:
        return word in cls.idiom_table

    @classmethod
    def is_syllable(cls, word: str) -> bool:
        return word in cls.syllables

    @classmethod
    def parse_syllables(cls, input_: str) -> list[tuple[str]] | None:
        # dp[i]: all possible syllables of seq[:i]
        parts = []
        delim = "-"
        for seq in re.split(r"[' \-]+", input_):
            dp: list[set[str]] = [set() for _ in range(len(seq) + 1)]
            dp[0] = {""}
            for i in range(1, len(seq) + 1):
                for s in cls.syllables:
                    if len(s) > i:
                        continue
                    # endswith this syllable and previous part is valid
                    # update dp[i] with all possible previous parts
                    if seq.endswith(s, 0, i) and dp[i - len(s)]:
                        dp[i].update([
                            f"{x}{delim}{s}" if x else s
                            for x in dp[i - len(s)]
                        ])
            if not dp[-1]:
                return
            parts.append([s.split(delim) for s in dp[-1]])
        return sorted(
            [
                sum([tuple(_) for _ in result], tuple())
                for result in product(*parts)
            ],
            key=lambda t: (len(t), t),
        )

    @classmethod
    def diff(cls, target: Sequence[T], provided: Sequence[T]) -> list[Diff]:
        if len(target) != len(provided):
            raise ValueError("Length of target and provided must be the same.")
        tc = Counter(target)
        result = []
        for t, p in zip(target, provided):
            if t == p:
                tc[t] -= 1
        for t, p in zip(target, provided):
            if t == p:
                result.append(Diff.EXACT)
            elif tc.get(p, 0) > 0:
                result.append(Diff.EXIST)
                tc[p] -= 1
            else:
                result.append(Diff.MISS)
        return result


Idiom.init()
