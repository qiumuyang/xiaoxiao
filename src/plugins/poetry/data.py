import re
import sqlite3
from pathlib import Path
from typing import TypedDict

import orjson


class PoetryItem(TypedDict):
    title: str
    dynasty: str
    author: str
    content: str


class Poetry:

    db_path = Path("~/.cache/nonebot/poetry.db").expanduser()
    poetry_path = Path("data/static/chinese/poetry")

    _conn: sqlite3.Connection | None = None

    p_pattern = re.compile(r"[,，\.。!！\?？、《》；]")

    dynasty = [
        "先秦", "秦", "汉", "魏晋", "魏晋末南北朝初", "南北朝", "隋", "隋末唐初", "唐", "唐末宋初", "宋",
        "辽", "宋末金初", "金", "宋末元初", "金末元初", "元", "元末明初", "明", "明末清初", "清",
        "清末民国初", "清末近现代初", "近现代", "民国末当代初", "近现代末当代初", "当代"
    ]

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
        CREATE TABLE IF NOT EXISTS poetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            dynasty TEXT,
            author TEXT,
            content TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS poetry_fts USING fts5(
            content, title, dynasty, author,
            content='poetry', content_rowid='id'
        );
        CREATE TABLE IF NOT EXISTS poetry_parts (
            part TEXT,
            poetry_id INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_part ON poetry_parts(part);
        """)
        conn.commit()

    @classmethod
    def init(cls):
        conn = cls.get_conn()
        if conn.execute("SELECT EXISTS("
                        "SELECT 1 FROM poetry LIMIT 1)").fetchone()[0]:
            return

        files = list(cls.poetry_path.glob("*.json"))
        items = []
        for file in files:
            items.extend(orjson.loads(file.read_bytes()))

        # Bulk insert in a single transaction
        with conn:
            # main table
            poetry_values = [(p["title"], p["dynasty"], p["author"],
                              p["content"]) for p in items]
            conn.executemany(
                "INSERT INTO poetry "
                "(title, dynasty, author, content) VALUES "
                "(?, ?, ?, ?)",
                poetry_values,
            )
            # retrieve all ids and contents
            rows = conn.execute(
                "SELECT id, content FROM poetry "
                "WHERE rowid <= last_insert_rowid()").fetchall()
            # build parts
            parts = []
            for row in rows:
                pid = row[0]
                for part in cls.separate(row[1]):
                    parts.append((part, pid))
            conn.executemany(
                "INSERT INTO poetry_parts "
                "(part, poetry_id) VALUES (?, ?)",
                parts,
            )
            # FTS index populate
            conn.execute(
                "INSERT INTO poetry_fts "
                "(rowid, content, title, dynasty, author)"
                " SELECT id, content, title, dynasty, author FROM poetry")

    @classmethod
    def search(cls, keyword: str) -> list[PoetryItem]:
        conn = cls.get_conn()
        cursor = conn.execute(
            "SELECT p.title, p.dynasty, p.author, p.content "
            "FROM poetry_fts f JOIN poetry p ON f.rowid = p.id "
            "WHERE poetry_fts MATCH ?",
            (keyword, ),
        )
        result = []
        for row in cursor:
            result.append({
                "title": row[0],
                "dynasty": row[1],
                "author": row[2],
                "content": row[3],
            })
        return result

    @classmethod
    def separate(cls, content: str) -> list[str]:
        return [s for s in cls.p_pattern.split(content) if s]

    @classmethod
    def search_origin(cls, content: str) -> list[PoetryItem]:
        parts = cls.separate(content)
        if not parts:
            return []
        conn = cls.get_conn()

        # get candidate ids by intersecting parts
        placeholder = ",".join("?" for _ in parts)
        query = (f"SELECT poetry_id FROM poetry_parts "
                 f"WHERE part IN ({placeholder}) "
                 f"GROUP BY poetry_id HAVING COUNT(DISTINCT part)=?")
        args = parts + [len(parts)]
        candidates = {r[0] for r in conn.execute(query, args)}
        if not candidates:
            return []

        # verify sequence match
        result = []
        sel = conn.execute(
            f"SELECT id, content, title, dynasty, author"
            f"FROM poetry WHERE id IN ({','.join('?' for _ in candidates)})",
            tuple(candidates),
        )
        for row in sel:
            _, poetry_content, title, dynasty, author = row
            pparts = cls.separate(poetry_content)
            # sliding window
            for i in range(len(pparts) - len(parts) + 1):
                if pparts[i:i + len(parts)] == parts:
                    result.append(
                        PoetryItem(title=title,
                                   dynasty=dynasty,
                                   author=author,
                                   content=poetry_content))
                    break
        return result


Poetry.init()
