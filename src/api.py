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
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from src import covers, db, launcher, scanner

# 表单允许写入/更新的列（与 db.UPDATABLE_FIELDS 一致）
FORM_FIELDS = ("name", "path", "exe", "args", "tags", "note")

RECENT_DAYS = 7


def _parse_time(value: str | None) -> datetime | None:
    """把 last_played 解析成 UTC aware datetime；空或无效返回 None。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def filter_recent(rows: list[dict[str, Any]],
                  now: datetime | None = None) -> list[dict[str, Any]]:
    """只保留近 1 周内启动过的游戏，按最后启动时间降序（最近的最前）。"""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RECENT_DAYS)
    timed: list[tuple[datetime, dict[str, Any]]] = []
    for row in rows:
        played = _parse_time(row.get("last_played"))
        if played is not None and played >= cutoff:
            timed.append((played, row))
    timed.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in timed]


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


def _default_image_picker(directory: str = "") -> str | None:
    """调用 pywebview 的图片选择框；没有窗口或取消返回 None。

    ``directory`` 为对话框初始目录（通常是游戏目录，方便用户自己挑图标）。
    """
    try:
        import webview
    except ImportError:
        return None
    if not webview.windows:
        return None
    result = webview.windows[0].create_file_dialog(
        webview.FileDialog.OPEN,
        directory=directory,
        file_types=("图片文件 (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif;*.ico)",),
    )
    if not result:
        return None
    return result[0] if isinstance(result, (tuple, list)) else str(result)


def _default_folder_opener(path: str) -> None:
    """用系统文件管理器打开目录（调用方已校验是存在的文件夹）。"""
    if platform.system() == "Windows":
        import os
        os.startfile(path)                       # noqa: S606 - 仅打开目录
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class Bridge:
    def __init__(self, database: db.GameDB | None = None,
                 directory_picker: Callable[[], list[str]] | None = None,
                 process_launcher: Callable[[dict[str, Any]],
                                           subprocess.Popen] | None = None,
                 image_picker: Callable[[str], str | None] | None = None,
                 folder_opener: Callable[[str], None] | None = None) -> None:
        # 不在构造时建表：让测试可以传入临时库而不产生副作用；
        # 真实启动时由 webapp.main() 调用 init()。
        self.database = database or db.GameDB()
        self.directory_picker = directory_picker or _default_directory_picker
        self.process_launcher = process_launcher or launcher.launch
        self.image_picker = image_picker or _default_image_picker
        self.folder_opener = folder_opener or _default_folder_opener
        self._running: dict[int, subprocess.Popen] = {}
        self._lock = threading.Lock()

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

        view="recent" 时只保留近 1 周内启动过的游戏，按最后启动时间降序。
        """
        options = options or {}
        rows = self.database.list(
            keyword=options.get("keyword", ""),
            tag=options.get("tag", ""),
        )
        if options.get("view") == "recent":
            return filter_recent(rows)
        return rows

    def get_game(self, game_id: int) -> dict[str, Any] | None:
        return self.database.get(game_id)

    def get_tags(self) -> list[dict[str, Any]]:
        """按库里实际出现的标签统计数量，供左栏按钮使用。"""
        counts: dict[str, int] = {}
        for row in self.database.list():
            for tag in db.split_tags(row["tags"]):
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

    # --- C2 封面 ---
    def get_cover(self, game_id: int) -> dict[str, Any]:
        """返回可直接放进 <img src> 的 data URI；无封面返回 ok=False。"""
        cover = self.database.get_cover(game_id)
        if cover is None:
            return {"ok": False, "error": "无封面"}
        blob, mime = cover
        return {"ok": True, "uri": covers.data_uri(blob, mime),
                "mime": mime, "bytes": len(blob)}

    def set_cover(self, game_id: int, file_path: str) -> dict[str, Any]:
        """从本地图片生成 WebP 缩略图并写入 BLOB。"""
        try:
            path = Path(file_path)
            if not path.is_file():
                return {"ok": False, "error": "文件不存在"}
            if path.suffix.lower() not in covers.IMAGE_SUFFIXES:
                return {"ok": False, "error": "不支持的图片格式"}
            blob, mime = covers.make_thumbnail(path.read_bytes())
            changed = self.database.set_cover(game_id, blob, mime)
            return {"ok": changed,
                    "error": "" if changed else "记录不存在",
                    "bytes": len(blob)}
        except (OSError, ValueError, RuntimeError) as exc:
            return {"ok": False, "error": str(exc)}

    def clear_cover(self, game_id: int) -> dict[str, Any]:
        return {"ok": self.database.clear_cover(game_id)}

    def find_cover_candidates(self, game_id: int) -> dict[str, Any]:
        """只读查找该游戏目录里的候选封面，绝不自动设置（由用户挑选）。"""
        row = self.database.get(game_id)
        if row is None:
            return {"ok": False, "error": "记录不存在", "paths": []}
        return {"ok": True, "paths": covers.discover_covers(row["path"])}

    def pick_image_file(self, game_id: int) -> str | None:
        """打开图片选择框，初始目录定位到该游戏目录，由用户自己挑选。

        返回所选文件路径；可注入假 picker（接收初始目录）便于测试。
        """
        row = self.database.get(game_id)
        directory = row["path"] if row and Path(row["path"]).is_dir() else ""
        return self.image_picker(directory)

    def open_folder(self, path: str) -> dict[str, Any]:
        """在系统文件管理器中打开该目录（只读动作，绝不执行任何文件）。"""
        raw = (path or "").strip()
        if not raw:                  # Path("") 会变成当前目录，必须先挡掉
            return {"ok": False, "error": "请先填写游戏目录"}
        target = Path(raw)
        if not target.is_dir():
            return {"ok": False, "error": "目录不存在或不是有效文件夹"}
        try:
            self.folder_opener(str(target))
        except OSError as exc:
            return {"ok": False, "error": f"无法打开目录: {exc}"}
        return {"ok": True}

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

    def scan_preview(self, roots: list[str],
                     max_depth: int = 2) -> dict[str, Any]:
        """只读扫描，按游戏目录分组返回候选（绝不入库、绝不执行任何文件）。

        ``candidates`` 保留扁平列表兼容旧调用方；``groups`` 供前端分组展示，
        每组带 recommended（只是默认勾选建议，不删任何候选）。
        """
        roots = [r for r in (roots or []) if r and r.strip()]
        if not roots:
            return {"ok": False, "error": "请先添加至少一个目录",
                    "candidates": [], "groups": []}
        found: list[scanner.Candidate] = []
        errors: list[str] = []
        valid_roots: list[Path] = []
        for item in roots:
            try:
                found.extend(scanner.scan(item, max_depth=max_depth))
                valid_roots.append(Path(item).resolve())
            except ValueError as exc:
                errors.append(str(exc))
        existing = {(r["path"], r["exe"]) for r in self.database.list()}
        fresh = scanner.filter_existing(scanner.dedupe(found), existing)

        # 嵌套的多个根目录时，候选只归给最深（最长路径）的那个
        owned_by_root: dict[Path, list[scanner.Candidate]] = {}
        for candidate in fresh:
            path = Path(candidate.path)
            owners = [r for r in valid_roots if path.is_relative_to(r)]
            if owners:
                owner = max(owners, key=lambda r: len(str(r)))
                owned_by_root.setdefault(owner, []).append(candidate)

        groups: list[dict[str, Any]] = []
        for root, owned in owned_by_root.items():
            for group in scanner.group_candidates(root, owned):
                groups.append({
                    "name": group.name,
                    "path": group.path,
                    "recommended": (None if group.recommended is None
                                    else group.recommended.exe),
                    "items": [{
                        "name": c.name,
                        "path": c.path,
                        "exe": c.exe,
                        "tool": scanner.is_tool_exe(c.exe),
                        "score": scanner.score_main(c, group.name, root),
                    } for c in group.candidates],
                })
        groups.sort(key=lambda g: g["name"].lower())
        return {
            "ok": True,
            "found": len(found),
            "candidates": [{"name": c.name, "path": c.path, "exe": c.exe}
                           for c in fresh],
            "groups": groups,
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

    # --- W4 启动与运行状态回传 ---
    def launch_game(self, game_id: int) -> dict[str, Any]:
        """启动指定游戏；成功即记一次游玩，失败给出明确错误。"""
        game = self.database.get(game_id)
        if game is None:
            return {"ok": False, "error": "游戏记录不存在"}
        try:
            process = self.process_launcher(game)
        except OSError as exc:
            return {"ok": False,
                    "error": f"{type(exc).__name__}: {exc}"}
        self.database.record_play(game_id)
        with self._lock:
            self._running[game_id] = process
        return {"ok": True, "running": True}

    def stop_game(self, game_id: int) -> dict[str, Any]:
        """停止运行中的游戏：终止进程并立即移出跟踪表。

        主动移出可避免下一次 poll_status 把「被用户停止」误报成异常退出。
        """
        with self._lock:
            process = self._running.pop(game_id, None)
        if process is None:
            return {"ok": False, "error": "该游戏未在运行"}
        try:
            process.terminate()
        except OSError as exc:
            return {"ok": False, "error": f"无法停止进程: {exc}"}
        return {"ok": True, "stopped": True}

    def poll_status(self) -> dict[str, Any]:
        """前端定时调用：收割已退出的进程并回传运行状态。

        用主线程轮询而非后台线程，避免跨线程操作 pywebview 窗口。
        """
        finished: list[dict[str, Any]] = []
        with self._lock:
            for game_id, process in list(self._running.items()):
                returncode = process.poll()
                if returncode is None:
                    continue
                del self._running[game_id]
                game = self.database.get(game_id)
                finished.append({
                    "id": game_id,
                    "name": game["name"] if game else "?",
                    "returncode": returncode,
                })
            running = list(self._running)
        return {
            "running": running,
            "finished": finished,
            "stats": self.get_stats(),
        }
