import re
import sqlite3
from pathlib import Path
from typing import TypedDict

import orjson

from src.utils.log import logger_wrapper

logger = logger_wrapper("poetry")


class PoetryItem(TypedDict):
    title: str
    dynasty: str
    author: str
    content: str


class Poetry:

    db_path = Path("~/.cache/nonebot/poetry.db").expanduser()
    poetry_path = Path("data/static/chinese/poetry")
    fix_path = Path("data/static/chinese/fix_poetry.txt")

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
    def init(cls, batch_size: int = 1000):
        conn = cls.get_conn()
        if not conn.execute("SELECT EXISTS("
                            "SELECT 1 FROM poetry LIMIT 1)").fetchone()[0]:
            files = list(cls.poetry_path.glob("*.json"))
            for file in files:
                poems = orjson.loads(file.read_bytes())
                batch_poetry = []
                batch_parts = []
                with conn:
                    for p in poems:
                        batch_poetry.append((p["title"], p["dynasty"],
                                             p["author"], p["content"]))
                        if len(batch_poetry) >= batch_size:
                            cls._insert_batch_in_tx(conn, batch_poetry,
                                                    batch_parts)
                            batch_poetry.clear()
                            batch_parts.clear()
                    if batch_poetry:
                        cls._insert_batch_in_tx(conn, batch_poetry,
                                                batch_parts)
        # always apply fix
        cls._apply_fix()

    @classmethod
    def _apply_fix(cls):
        if not cls.fix_path.exists():
            return

        conn = cls.get_conn()
        with conn:
            raw = cls.fix_path.read_text(encoding="utf-8")
            for entry in raw.split("====="):
                lines = [
                    _ for line in entry.strip().splitlines()
                    if (_ := line.strip())
                ]
                if len(lines) != 2:
                    logger.warning(f"Skipping invalid entry: \n{entry}")
                    continue
                original, repl = lines
                row = conn.execute(
                    "SELECT id, content FROM poetry WHERE content=?",
                    (original, ),
                ).fetchone()
                if row:
                    poetry_id = row[0]
                    conn.execute(
                        "UPDATE poetry SET content=? WHERE id=?",
                        (repl, poetry_id),
                    )
                    conn.execute("DELETE FROM poetry_fts WHERE rowid = ?",
                                 (poetry_id, ))
                    conn.execute(
                        "INSERT INTO poetry_fts "
                        "(rowid, content, title, dynasty, author)"
                        " SELECT id, content, title, dynasty, author FROM poetry "
                        "WHERE id = ?", (poetry_id, ))
                    conn.execute(
                        "DELETE FROM poetry_parts WHERE poetry_id=?",
                        (poetry_id, ),
                    )
                    for part in cls.separate(repl):
                        conn.execute(
                            "INSERT INTO poetry_parts "
                            "(part, poetry_id) VALUES (?, ?)",
                            (part, poetry_id),
                        )
                    logger.info(f"Fixed poetry {poetry_id}: \n"
                                f"   {original}\n"
                                f"-> {repl}")

    @classmethod
    def _insert_batch_in_tx(cls, conn: sqlite3.Connection, batch_poetry,
                            batch_parts):
        # main table
        conn.executemany(
            "INSERT INTO poetry "
            "(title, dynasty, author, content) VALUES (?, ?, ?, ?)",
            batch_poetry,
        )

        last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        start_id = last_id - len(batch_poetry) + 1

        for offset, poetry in enumerate(batch_poetry):
            pid = start_id + offset
            for part in cls.separate(poetry[3]):
                batch_parts.append((part, pid))

        conn.executemany(
            "INSERT INTO poetry_parts "
            "(part, poetry_id) VALUES (?, ?)",
            batch_parts,
        )
        # FTS index populate
        conn.execute(
            "INSERT INTO poetry_fts "
            "(rowid, content, title, dynasty, author)"
            " SELECT id, content, title, dynasty, author FROM poetry "
            "WHERE id BETWEEN ? AND ?", (start_id, last_id))

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
            f"SELECT id, content, title, dynasty, author "
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
