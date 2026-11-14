"""游戏库数据层：SQLite 单文件存储，只用标准库。"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src import paths, pinyin  # noqa: E402

DEFAULT_DB_PATH = paths.data_dir() / "games.db"

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
    cover       BLOB,
    cover_mime  TEXT    NOT NULL DEFAULT '',
    UNIQUE (path, exe)
);
CREATE INDEX IF NOT EXISTS idx_games_name ON games (name);
"""

# 列表/详情返回的列：故意不含 cover BLOB，避免把图片字节塞进前端响应
_LIST_COLUMNS = ("id", "name", "path", "exe", "args", "tags", "note",
                 "added_at", "last_played", "play_count")
_SELECT = (", ".join(_LIST_COLUMNS)
           + ", (cover IS NOT NULL AND length(cover) > 0) AS has_cover")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_TAG_SEPARATORS = re.compile(r"[,，]+")


def split_tags(tags: str) -> list[str]:
    """按中英文逗号拆分标签；顿号、分号、空格等一律视为标签内容。"""
    return [t.strip() for t in _TAG_SEPARATORS.split(tags or "") if t.strip()]


def _normalize_tags(tags: str) -> str:
    return ",".join(split_tags(tags))


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
        """建表并幂等补齐封面列，可重复调用（老库不丢数据）。"""
        with self._session() as conn:
            conn.executescript(_SCHEMA)
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(games)")}
            if "cover" not in cols:
                conn.execute("ALTER TABLE games ADD COLUMN cover BLOB")
            if "cover_mime" not in cols:
                conn.execute("ALTER TABLE games ADD COLUMN cover_mime "
                             "TEXT NOT NULL DEFAULT ''")

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
                f"SELECT {_SELECT} FROM games WHERE id = ?", (game_id,)
            ).fetchone()
            return dict(row) if row is not None else None

    def get_cover(self, game_id: int) -> tuple[bytes, str] | None:
        """读取封面缩略图字节与 MIME；无封面或 id 不存在返回 None。"""
        with self._session() as conn:
            row = conn.execute(
                "SELECT cover, cover_mime FROM games WHERE id = ?", (game_id,)
            ).fetchone()
        if row is None or row["cover"] is None:
            return None
        return bytes(row["cover"]), row["cover_mime"]

    def set_cover(self, game_id: int, blob: bytes, mime: str) -> bool:
        """写入封面缩略图（字节由桥接层用 Pillow 生成）。"""
        if not blob:
            return self.clear_cover(game_id)
        with self._session() as conn:
            cur = conn.execute(
                "UPDATE games SET cover = ?, cover_mime = ? WHERE id = ?",
                (sqlite3.Binary(blob), mime, game_id),
            )
            return cur.rowcount > 0

    def clear_cover(self, game_id: int) -> bool:
        with self._session() as conn:
            cur = conn.execute(
                "UPDATE games SET cover = NULL, cover_mime = '' WHERE id = ?",
                (game_id,),
            )
            return cur.rowcount > 0

    def record_play(self, game_id: int) -> bool:
        """记一次游玩：写最后游玩时间、次数 +1；id 不存在返回 False。"""
        with self._session() as conn:
            cur = conn.execute(
                "UPDATE games SET last_played = ?, play_count = play_count + 1 "
                "WHERE id = ?",
                (_now(), game_id),
            )
            return cur.rowcount > 0

    def list(self, keyword: str = "", tag: str = "") -> list[dict[str, Any]]:
        """按名称（中文 / 全拼 / 首字母）前缀搜索，再按标签前缀过滤，按名称排序。"""
        with self._session() as conn:
            rows = [dict(r) for r in conn.execute(
                f"SELECT {_SELECT} FROM games "
                "ORDER BY name COLLATE NOCASE, id").fetchall()]
        if keyword.strip():
            rows = [r for r in rows if pinyin.match(r["name"], keyword)]
        if tag.strip():
            wanted = tag.strip().casefold()
            rows = [r for r in rows
                    if any(t.casefold().startswith(wanted)
                           for t in split_tags(r["tags"]))]
        return rows
