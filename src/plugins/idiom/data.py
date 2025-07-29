"""Idiom data from https://github.com/pwxcoo/chinese-xinhua"""

import random
import re
import sqlite3
from collections import Counter
from enum import Enum
from itertools import product
from pathlib import Path
from typing import Hashable, Sequence, TypedDict, TypeVar

import orjson
from pypinyin import Style as PinyinStyle
from pypinyin import lazy_pinyin, load_phrases_dict

from src.utils.log import logger_wrapper

logger = logger_wrapper("idiom")


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

    db_path = Path("~/.cache/nonebot/idiom.db").expanduser()
    idiom_path = Path("data/static/chinese/idiom.json")
    fix_path = Path("data/static/chinese/fix_pinyin.txt")
    syllable_path = Path("data/static/chinese/syllables.txt")

    _conn: sqlite3.Connection | None = None
    syllables: set[str] = set()
    SEP = "-"

    @classmethod
    def get_conn(cls) -> sqlite3.Connection:
        if cls._conn is None:
            cls.db_path.parent.mkdir(parents=True, exist_ok=True)
            cls._conn = sqlite3.connect(cls.db_path)
            cls._conn.execute("PRAGMA journal_mode=WAL")
            cls._conn.execute("PRAGMA synchronous=NORMAL")
            cls._init_db()
        return cls._conn

    @classmethod
    def _init_db(cls):
        conn = cls.get_conn()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS idiom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE,
            pinyin TEXT,
            pinyin_tone TEXT,
            explanation TEXT,
            example TEXT,
            derivation TEXT,
            length INTEGER
        );
        """)
        conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_idiom_word ON idiom(word);
        CREATE INDEX IF NOT EXISTS idx_idiom_length ON idiom(length);
        """)
        conn.commit()

    @classmethod
    def init(cls):
        conn = cls.get_conn()

        # ==== fix pinyin ====
        fix_dict: dict[str, list[list[str]]] = {}
        removes = set()
        for line in cls.fix_path.read_text(encoding="utf-8").splitlines():
            word, *syllables = line.strip().split()
            if not syllables:
                removes.add(word)
                continue
            fix_dict[word] = [[s] for s in syllables]
        load_phrases_dict(fix_dict)

        # If empty, load idioms
        if not conn.execute(
                "SELECT EXISTS(SELECT 1 FROM idiom LIMIT 1)").fetchone()[0]:
            items = orjson.loads(cls.idiom_path.read_bytes())
            with conn:
                for item in items:
                    word = item["word"]
                    if word in removes:
                        continue
                    pinyin = lazy_pinyin(word, style=PinyinStyle.NORMAL)
                    pinyin_tone = lazy_pinyin(word, style=PinyinStyle.TONE)
                    explanation = item["explanation"].replace("”", "")
                    example = item["example"].replace("”", "")
                    derivation = item["derivation"].replace("”", "").replace(
                        "无", "")

                    conn.execute(
                        "INSERT INTO idiom (word, pinyin, pinyin_tone, explanation, example, derivation, length)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            word,
                            cls.SEP.join(pinyin),
                            cls.SEP.join(pinyin_tone),
                            explanation,
                            example,
                            derivation,
                            len(word),
                        ),
                    )
        else:
            # If not empty, update pinyin
            with conn:
                for word in fix_dict:
                    pinyin = lazy_pinyin(word, style=PinyinStyle.NORMAL)
                    pinyin_tone = lazy_pinyin(word, style=PinyinStyle.TONE)
                    conn.execute(
                        "UPDATE idiom SET pinyin = ?, pinyin_tone = ? WHERE word = ?",
                        (cls.SEP.join(pinyin), cls.SEP.join(pinyin_tone),
                         word),
                    )
                for word in removes:
                    conn.execute("DELETE FROM idiom WHERE word = ?", (word, ))

        # syllables
        for line in cls.syllable_path.read_text(encoding="utf-8").splitlines():
            if s := line.strip():
                cls.syllables.add(s)

    @classmethod
    def random4(cls, excludes: set[str] = set()) -> IdiomItem:
        conn = cls.get_conn()
        cursor = conn.execute(
            "SELECT word, pinyin, pinyin_tone, explanation, example, derivation "
            "FROM idiom WHERE rowid IN ("
            "    SELECT rowid FROM idiom WHERE length = 4 "
            "    ORDER BY RANDOM() LIMIT ?"
            ")", (max(100,
                      len(excludes) + 1), ))
        idioms = [row for row in cursor if row[0] not in excludes]
        if not idioms:
            logger.error("No idiom available.")
            raise ValueError
        word, pinyin, pinyin_tone, explanation, example, derivation = random.choice(
            idioms)
        return IdiomItem(
            word=word,
            pinyin=pinyin.split(cls.SEP),
            pinyin_tone=pinyin_tone.split(cls.SEP),
            explanation=explanation,
            example=example,
            derivation=derivation,
        )

    @classmethod
    def get_pinyin(cls, word: str, tone: bool = False) -> list[str]:
        conn = cls.get_conn()
        row = conn.execute(
            "SELECT pinyin, pinyin_tone FROM idiom WHERE word = ?",
            (word, )).fetchone()
        if not row:
            raise ValueError(f"Not an idiom: {word}")
        pinyin, pinyin_tone = row
        return (pinyin_tone if tone else pinyin).split(cls.SEP)

    @classmethod
    def is_idiom(cls, word: str) -> bool:
        conn = cls.get_conn()
        row = conn.execute("SELECT 1 FROM idiom WHERE word = ?",
                           (word, )).fetchone()
        return row is not None

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

    @classmethod
    def load_idiom(cls, word: str) -> IdiomItem:
        conn = cls.get_conn()
        row = conn.execute(
            "SELECT word, pinyin, pinyin_tone, explanation, example, derivation "
            "FROM idiom WHERE word = ?", (word, )).fetchone()
        if not row:
            raise ValueError(f"Not an idiom: {word}")
        return IdiomItem(
            word=row[0],
            pinyin=row[1].split(cls.SEP),
            pinyin_tone=row[2].split(cls.SEP),
            explanation=row[3],
            example=row[4],
            derivation=row[5],
        )


Idiom.init()
