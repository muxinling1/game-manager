"""标签分隔符与前缀匹配筛选的回归测试。"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, db  # noqa: E402


class SplitTagsTests(unittest.TestCase):
    def test_only_comma_and_fullwidth_comma_split(self):
        self.assertEqual(db.split_tags("动作,独立，RPG"),
                         ["动作", "独立", "RPG"])

    def test_other_punctuation_stays_inside_tag(self):
        self.assertEqual(db.split_tags("第一人称射击、单人游戏;建造及自动化"),
                         ["第一人称射击、单人游戏;建造及自动化"])

    def test_spaces_trimmed_but_not_separators(self):
        self.assertEqual(db.split_tags(" 3D 横板 , 动作 "), ["3D 横板", "动作"])

    def test_empty(self):
        self.assertEqual(db.split_tags(""), [])
        self.assertEqual(db.split_tags(",,，"), [])


class TagFilterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbfile = Path(self.tmp.name) / "g.db"
        self.database = db.GameDB(self.dbfile)
        self.database.init()
        self.bridge = api.Bridge(self.database)

    def tearDown(self):
        self.tmp.cleanup()

    def _add(self, name, tags):
        return self.database.add(name=name, path=f"P/{name}",
                                 exe=f"{name}.exe", tags=tags)

    def test_fullwidth_comma_normalized_on_write(self):
        gid = self._add("A", "第一人称射击，搜打撤，多人游戏")
        self.assertEqual(self.database.get(gid)["tags"],
                         "第一人称射击,搜打撤,多人游戏")

    def test_historical_fullwidth_data_still_filterable(self):
        """未迁移的历史数据（中文逗号）读取时也要能正确筛选。"""
        con = sqlite3.connect(str(self.dbfile))
        con.execute(
            "INSERT INTO games (name,path,exe,args,tags,note,added_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("B", "P/B", "b.exe", "", "第一人称射击，单人游戏", "",
             "2026-01-01T00:00:00+00:00"))
        con.commit()
        con.close()
        self.assertEqual(
            [r["name"] for r in self.database.list(tag="第一人称射击")], ["B"])

    def test_prefix_match(self):
        self._add("A", "第一人称射击")
        self._add("B", "第一人称射击")
        self._add("C", "RPG")
        self.assertEqual({r["name"] for r in self.database.list(tag="第一")},
                         {"A", "B"})
        self.assertEqual([r["name"] for r in self.database.list(tag="R")], ["C"])

    def test_prefix_is_case_insensitive(self):
        self._add("A", "RPG")
        self.assertEqual([r["name"] for r in self.database.list(tag="rpg")], ["A"])
        self.assertEqual([r["name"] for r in self.database.list(tag="rp")], ["A"])

    def test_get_tags_counts_split_fullwidth(self):
        self._add("A", "第一人称射击，搜打撤")
        self._add("B", "第一人称射击，单人游戏")
        got = {t["name"]: t["count"] for t in self.bridge.get_tags()}
        self.assertEqual(got.get("第一人称射击"), 2)
        self.assertEqual(got.get("搜打撤"), 1)

    def test_other_punctuation_not_split_in_get_tags(self):
        self._add("A", "建造及自动化、模拟")
        self.assertIn("建造及自动化、模拟",
                      [t["name"] for t in self.bridge.get_tags()])

    def test_prefix_via_bridge(self):
        self._add("A", "第一人称射击")
        self._add("B", "RPG")
        self.assertEqual(
            [r["name"] for r in self.bridge.list_games({"tag": "第一"})], ["A"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
