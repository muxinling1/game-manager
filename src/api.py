"""C2 桥接层：这些方法暴露给前端，成为 ``window.pywebview.api``。

W1: get_version / ping 探针
W2: 只读查询（列表、搜索、标签、统计、详情）
W3: 增删改与扫描导入
W4: 启动与运行状态回传

前端不需要 HTTP 服务，pywebview 通过 js_api 做进程内直调。
"""

from __future__ import annotations

import platform
from typing import Any

from src import db


class Bridge:
    def __init__(self, database: db.GameDB | None = None) -> None:
        # 不在构造时建表：让测试可以传入临时库而不产生副作用；
        # 真实启动时由 webapp.main() 调用 init()。
        self.database = database or db.GameDB()

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
