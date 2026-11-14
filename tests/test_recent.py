"""「最近游玩」视图：近 1 周筛选 + 按最后启动时间降序。"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, db  # noqa: E402

NOW = datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class FilterRecentTests(unittest.TestCase):
    def _row(self, name, days_ago=None):
        return {"name": name,
                "last_played": _iso(NOW - timedelta(days=days_ago))
                if days_ago is not None else None}

    def test_only_last_seven_days(self):
        rows = [self._row("今天", 0), self._row("三天前", 3),
                self._row("刚好七天", 7), self._row("八天前", 8),
                self._row("从未启动")]
        out = [r["name"] for r in api.filter_recent(rows, now=NOW)]
        self.assertEqual(out, ["今天", "三天前", "刚好七天"])

    def test_most_recent_first(self):
        rows = [self._row("旧", 5), self._row("新", 0), self._row("中", 2)]
        self.assertEqual(
            [r["name"] for r in api.filter_recent(rows, now=NOW)],
            ["新", "中", "旧"])

    def test_expired_and_never_played_excluded(self):
        rows = [self._row("八天前", 8), self._row("从未启动"),
                self._row("一个月前", 30)]
        self.assertEqual(api.filter_recent(rows, now=NOW), [])

    def test_invalid_timestamp_ignored(self):
        rows = [{"name": "坏数据", "last_played": "not-a-date"},
                self._row("正常", 1)]
        self.assertEqual(
            [r["name"] for r in api.filter_recent(rows, now=NOW)], ["正常"])

    def test_naive_timestamp_treated_as_utc(self):
        rows = [{"name": "无时区", "last_played": "2026-11-13T10:00:00"}]
        self.assertEqual(
            [r["name"] for r in api.filter_recent(rows, now=NOW)], ["无时区"])


class BridgeRecentViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbfile = Path(self.tmp.name) / "g.db"
        self.database = db.GameDB(self.dbfile)
        self.database.init()
        self.bridge = api.Bridge(self.database)

    def tearDown(self):
        self.tmp.cleanup()

    def _add(self, name, days_ago=None):
        gid = self.database.add(name=name, path="P/" + name,
                                exe=name + ".exe")
        if days_ago is not None:
            played = _iso(datetime.now(timezone.utc)
                          - timedelta(days=days_ago))
            con = sqlite3.connect(str(self.dbfile))
            con.execute(
                "UPDATE games SET last_played = ?, play_count = 1 WHERE id = ?",
                (played, gid))
            con.commit()
            con.close()
        return gid

    def test_recent_view_filters_and_orders(self):
        self._add("今天", 0)
        self._add("两天前", 2)
        self._add("九天前", 9)
        self._add("从未启动")
        names = [r["name"] for r in self.bridge.list_games({"view": "recent"})]
        self.assertEqual(names, ["今天", "两天前"])
        # 普通视图不受影响，仍显示全部
        self.assertEqual(len(self.bridge.list_games({"view": "all"})), 4)

    def test_recent_composes_with_keyword_and_tag(self):
        g1 = self._add("最近动作", 1)
        self.database.update(g1, tags="动作")
        g2 = self._add("最近独立", 1)
        self.database.update(g2, tags="独立")
        g3 = self._add("过期动作", 9)
        self.database.update(g3, tags="动作")
        rows = self.bridge.list_games({"view": "recent", "tag": "动作"})
        self.assertEqual([r["name"] for r in rows], ["最近动作"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
