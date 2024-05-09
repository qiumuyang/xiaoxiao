import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import orjson


class PoetryItem(TypedDict):
    title: str
    dynasty: str
    author: str
    content: str


class Poetry:

    poetry_table: list[PoetryItem] = []

    # map part to poetry
    reverse_db: sqlite3.Connection | None = None
    reverse_path = "~/.cache/nonebot/poetry_reverse.db"

    p_pattern = re.compile(r"[,，\.。!！\?？、《》；]")

    @classmethod
    def init(cls):
        root = Path("data/static/chinese/poetry")
        for file in root.glob("*.json"):
            cls.poetry_table.extend(orjson.loads(file.read_bytes()))
        cls._init_reverse_db()

    @classmethod
    def _init_reverse_db(cls):
        if cls.reverse_db is not None:
            return
        db_path = Path(cls.reverse_path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        cls.reverse_db = sqlite3.connect(db_path)
        if cls.reverse_db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='poetry'"
        ).fetchone():
            return

        cls.reverse_db.execute("CREATE TABLE poetry (part TEXT, idx INT)")
        cls.reverse_db.execute("CREATE INDEX part_index ON poetry (part, idx)")
        cls.reverse_db.commit()

        buffer = []
        limit = 10000
        for i, poetry in enumerate(cls.poetry_table):
            for part in cls.separate(poetry["content"]):
                buffer.append((part, i))
            if len(buffer) >= limit:
                cls.reverse_db.executemany("INSERT INTO poetry VALUES (?, ?)",
                                           buffer)
                buffer.clear()
        if buffer:
            cls.reverse_db.executemany("INSERT INTO poetry VALUES (?, ?)",
                                       buffer)
        cls.reverse_db.commit()

    @classmethod
    @lru_cache(maxsize=64)
    def search(cls, keyword: str) -> list[PoetryItem]:
        return [p for p in cls.poetry_table if keyword in p["content"]]

    @classmethod
    def separate(cls, content: str) -> list[str]:
        return [s for s in cls.p_pattern.split(content) if s]

    @classmethod
    def search_origin(cls, content: str) -> list[PoetryItem]:
        parts = cls.separate(content)
        if not parts:
            return []
        assert cls.reverse_db is not None
        indices = cls.reverse_db.execute(
            "SELECT idx FROM poetry WHERE part = ?", (parts[0], )).fetchall()
        result = []
        for i in indices:
            poetry = cls.poetry_table[i[0]]
            poetry_parts = cls.separate(poetry["content"])
            for j in range(len(poetry_parts) - len(parts) + 1):
                if poetry_parts[j:j + len(parts)] == parts:
                    result.append(poetry)
                    break
        return result


Poetry.init()
