"""C2 桥接层：这些方法暴露给前端，成为 ``window.pywebview.api``。

W1: get_version / ping 探针
W2: 只读查询（列表、搜索、标签、统计、详情）
W3: 增删改与扫描导入
W4: 启动与运行状态回传

前端不需要 HTTP 服务，pywebview 通过 js_api 做进程内直调。
所有写操作返回 {"ok": bool, ...}，把异常转成可显示的错误，不让 Promise 抛飞。
"""

from __future__ import annotations

import platform
import sqlite3
from typing import Any, Callable

from src import db, scanner

# 表单允许写入/更新的列（与 db.UPDATABLE_FIELDS 一致）
FORM_FIELDS = ("name", "path", "exe", "args", "tags", "note")


def _clean(fields: dict[str, Any] | None) -> dict[str, str]:
    fields = fields or {}
    return {key: str(fields.get(key) or "") for key in FORM_FIELDS}


def _default_directory_picker() -> list[str]:
    """调用 pywebview 的目录选择框；没有窗口时返回空列表。"""
    try:
        import webview
    except ImportError:
        return []
    if not webview.windows:
        return []
    result = webview.windows[0].create_file_dialog(
        webview.FOLDER_DIALOG, allow_multiple=True)
    if not result:
        return []
    return [result] if isinstance(result, str) else list(result)


class Bridge:
    def __init__(self, database: db.GameDB | None = None,
                 directory_picker: Callable[[], list[str]] | None = None) -> None:
        # 不在构造时建表：让测试可以传入临时库而不产生副作用；
        # 真实启动时由 webapp.main() 调用 init()。
        self.database = database or db.GameDB()
        self.directory_picker = directory_picker or _default_directory_picker

    def init(self) -> None:
        self.database.init()

    # --- W1 探针（保留，前端用它确认桥接是否打通） ---
    def get_version(self) -> str:
        return f"Python {platform.python_version()}"

    def ping(self) -> str:
        return "pong"

    # --- W2 只读查询 ---
    def list_games(self, options: dict[str, Any] | None = None
                   ) -> list[dict[str, Any]]:
        """按关键字/标签过滤，返回可直接渲染的行。

        view="recent" 时按最后游玩时间降序（与旧 tkinter 版一致）。
        """
        options = options or {}
        rows = self.database.list(
            keyword=options.get("keyword", ""),
            tag=options.get("tag", ""),
        )
        if options.get("view") == "recent":
            rows.sort(key=lambda r: r["last_played"] or "", reverse=True)
        return rows

    def get_game(self, game_id: int) -> dict[str, Any] | None:
        return self.database.get(game_id)

    def get_tags(self) -> list[dict[str, Any]]:
        """按库里实际出现的标签统计数量，供左栏按钮使用。"""
        counts: dict[str, int] = {}
        for row in self.database.list():
            for tag in (t.strip() for t in row["tags"].split(",")):
                if tag:
                    counts[tag] = counts.get(tag, 0) + 1
        return [{"name": name, "count": counts[name]}
                for name in sorted(counts)]

    def get_stats(self) -> dict[str, int]:
        """统计盒数据，全部来自真实库。"""
        rows = self.database.list()
        return {
            "total": len(rows),
            "played": sum(1 for r in rows if r["play_count"] > 0),
            "launches": sum(r["play_count"] for r in rows),
        }

    # --- W3 增删改 ---
    def add_game(self, fields: dict[str, Any]) -> dict[str, Any]:
        try:
            game_id = self.database.add(**_clean(fields))
            return {"ok": True, "id": game_id}
        except (ValueError, sqlite3.IntegrityError) as exc:
            return {"ok": False, "error": str(exc)}

    def update_game(self, game_id: int,
                    fields: dict[str, Any]) -> dict[str, Any]:
        try:
            changed = self.database.update(game_id, **_clean(fields))
            return {"ok": changed, "error": "" if changed else "记录不存在"}
        except (ValueError, sqlite3.IntegrityError) as exc:
            return {"ok": False, "error": str(exc)}

    def delete_game(self, game_id: int) -> dict[str, Any]:
        return {"ok": self.database.delete(game_id)}

    # --- W3 扫描导入 ---
    def pick_directories(self) -> list[str]:
        """返回用户选中的目录；可注入假 picker 便于测试。"""
        return list(self.directory_picker() or [])

    def scan_preview(self, roots: list[str]) -> dict[str, Any]:
        """只读扫描，返回候选（绝不入库、绝不执行任何文件）。"""
        roots = [r for r in (roots or []) if r and r.strip()]
        if not roots:
            return {"ok": False, "error": "请先添加至少一个目录", "candidates": []}
        found: list[scanner.Candidate] = []
        errors: list[str] = []
        for root in roots:
            try:
                found.extend(scanner.scan(root))
            except ValueError as exc:
                errors.append(str(exc))
        existing = {(r["path"], r["exe"]) for r in self.database.list()}
        fresh = scanner.filter_existing(scanner.dedupe(found), existing)
        return {
            "ok": True,
            "found": len(found),
            "candidates": [{"name": c.name, "path": c.path, "exe": c.exe}
                           for c in fresh],
            "errors": errors,
        }

    def import_games(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """只有前端勾选并提交的候选才会入库。"""
        imported = 0
        skipped = 0
        for item in items or []:
            try:
                self.database.add(
                    name=item["name"], path=item["path"], exe=item["exe"])
                imported += 1
            except (KeyError, ValueError, sqlite3.IntegrityError):
                skipped += 1
        return {"ok": True, "imported": imported, "skipped": skipped}
