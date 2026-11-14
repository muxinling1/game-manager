"""W2 桥接层测试：只读查询全部基于真实临时库，不弹窗口。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, db  # noqa: E402


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dbfile = Path(self.tmp.name) / "games.db"
        self.database = db.GameDB(self.dbfile)
        self.bridge = api.Bridge(self.database)
        self.bridge.init()

    def _add(self, name, tags="", path=None, exe=None, plays=0):
        gid = self.database.add(
            name=name, path=path or f"D:/Games/{name}",
            exe=exe or f"{name}.exe", tags=tags)
        for _ in range(plays):
            self.database.record_play(gid)
        return gid

    def test_construct_does_not_create_db_file(self):
        fresh = api.Bridge(db.GameDB(Path(self.tmp.name) / "fresh.db"))
        self.assertFalse((Path(self.tmp.name) / "fresh.db").exists())
        fresh.init()   # 幂等
        fresh.init()
        self.assertTrue((Path(self.tmp.name) / "fresh.db").exists())

    def test_probe_methods(self):
        self.assertTrue(self.bridge.get_version().startswith("Python "))
        self.assertEqual(self.bridge.ping(), "pong")

    def test_list_games_empty(self):
        self.assertEqual(self.bridge.list_games(), [])
        self.assertEqual(self.bridge.list_games({}), [])

    def test_list_games_keyword_and_tag(self):
        self._add("Alpha", tags="动作, 独立", plays=2)
        self._add("Beta", tags="独立", plays=1)
        self._add("Gamma", tags="角色扮演")
        rows = self.bridge.list_games({"keyword": "Beta"})
        self.assertEqual([r["name"] for r in rows], ["Beta"])
        rows = self.bridge.list_games({"tag": "独立"})
        self.assertEqual({r["name"] for r in rows}, {"Alpha", "Beta"})
        self.assertEqual(len(self.bridge.list_games()), 3)

    def test_list_games_recent_only_shows_recently_played(self):
        self._add("Alpha")            # 从未启动 → 排除
        self._add("Beta", plays=1)    # 刚启动过 → 保留
        self.assertEqual(
            [r["name"] for r in self.bridge.list_games({"view": "all"})],
            ["Alpha", "Beta"])
        self.assertEqual(
            [r["name"] for r in self.bridge.list_games({"view": "recent"})],
            ["Beta"])

    def test_get_tags_counts_real_data(self):
        self._add("A", tags="动作, 独立")
        self._add("B", tags="动作")
        self._add("C", tags="")
        self.assertEqual(self.bridge.get_tags(), [
            {"name": "动作", "count": 2},
            {"name": "独立", "count": 1},
        ])

    def test_get_stats(self):
        self._add("A", plays=2)
        self._add("B", plays=1)
        self._add("C")
        self.assertEqual(self.bridge.get_stats(), {
            "total": 3, "played": 2, "launches": 3,
        })

    def test_get_game(self):
        gid = self._add("Demo", tags="独立", plays=3)
        row = self.bridge.get_game(gid)
        self.assertEqual(row["name"], "Demo")
        self.assertEqual(row["play_count"], 3)
        self.assertIsNone(self.bridge.get_game(999999))


if __name__ == "__main__":
    unittest.main(verbosity=2)
