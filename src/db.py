"""游戏库数据层：SQLite 单文件存储，只用标准库。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "games.db"

# update() 允许改动的列；列名只能从这里取，避免拼接 SQL 时被注入
UPDATABLE_FIELDS = ("name", "path", "exe", "args", "tags", "note")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    path        TEXT    NOT NULL,
    exe         TEXT    NOT NULL,
    args        TEXT    NOT NULL DEFAULT '',
    tags        TEXT    NOT NULL DEFAULT '',
    note        TEXT    NOT NULL DEFAULT '',
    added_at    TEXT    NOT NULL,
    last_played TEXT,
    play_count  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (path, exe)
);
CREATE INDEX IF NOT EXISTS idx_games_name ON games (name);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_tags(tags: str) -> str:
    return ",".join(t.strip() for t in tags.split(",") if t.strip())


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class GameDB:
    """每次操作独立开关连接，因此 GUI 的后台线程也能安全调用。"""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        """建表，可重复调用。"""
        with self._session() as conn:
            conn.executescript(_SCHEMA)

    def add(self, *, name: str, path: str, exe: str,
            args: str = "", tags: str = "", note: str = "") -> int:
        """新增一条游戏并返回 id；(path, exe) 重复会抛 sqlite3.IntegrityError。"""
        for label, value in (("name", name), ("path", path), ("exe", exe)):
            if not value or not value.strip():
                raise ValueError(f"{label} 不能为空")
        with self._session() as conn:
            cur = conn.execute(
                "INSERT INTO games (name, path, exe, args, tags, note, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name.strip(), path.strip(), exe.strip(),
                 args, _normalize_tags(tags), note, _now()),
            )
            return int(cur.lastrowid)

    def update(self, game_id: int, **fields: Any) -> bool:
        """按 id 更新白名单内的列；id 不存在返回 False。"""
        unknown = set(fields) - set(UPDATABLE_FIELDS)
        if unknown:
            raise ValueError(f"不可更新字段: {', '.join(sorted(unknown))}")
        if not fields:
            return False
        fields = dict(fields)
        if "tags" in fields:
            fields["tags"] = _normalize_tags(str(fields["tags"]))
        assignments = ", ".join(f"{col} = ?" for col in fields)
        with self._session() as conn:
            cur = conn.execute(
                f"UPDATE games SET {assignments} WHERE id = ?",
                (*fields.values(), game_id),
            )
            return cur.rowcount > 0

    def delete(self, game_id: int) -> bool:
        with self._session() as conn:
            cur = conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
            return cur.rowcount > 0

    def get(self, game_id: int) -> dict[str, Any] | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM games WHERE id = ?", (game_id,)
            ).fetchone()
            return dict(row) if row is not None else None

    def list(self, keyword: str = "", tag: str = "") -> list[dict[str, Any]]:
        """按名称/路径/备注模糊搜索，再按标签精确过滤，结果按名称排序。"""
        sql = "SELECT * FROM games"
        params: list[Any] = []
        if keyword.strip():
            sql += (" WHERE (name LIKE ? ESCAPE '\\' OR path LIKE ? ESCAPE '\\' "
                    "OR note LIKE ? ESCAPE '\\')")
            like = f"%{_escape_like(keyword.strip())}%"
            params.extend((like, like, like))
        sql += " ORDER BY name COLLATE NOCASE, id"
        with self._session() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        if tag.strip():
            wanted = tag.strip()
            rows = [r for r in rows
                    if wanted in [t.strip() for t in r["tags"].split(",")]]
        return rows
