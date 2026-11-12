"""F1 数据层测试。

运行：python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db  # noqa: E402


class GameDBTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = db.GameDB(Path(self.tmp.name) / "games.db")
        self.db.init()

    def _add(self, name="测试游戏", path=r"D:\Games\Demo", exe="demo.exe", **kw):
        return self.db.add(name=name, path=path, exe=exe, **kw)

    def test_init_creates_table_and_is_idempotent(self):
        self.db.init()  # 重复建表不应报错
        conn = sqlite3.connect(self.db.db_path)
        try:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
        finally:
            conn.close()
        self.assertIn("games", tables)

    def test_add_and_get(self):
        gid = self._add(note="备注", tags="动作, 独立")
        row = self.db.get(gid)
        self.assertEqual(row["name"], "测试游戏")
        self.assertEqual(row["tags"], "动作,独立")
        self.assertEqual(row["note"], "备注")
        self.assertEqual(row["play_count"], 0)
        self.assertIsNone(row["last_played"])
        self.assertTrue(row["added_at"])

    def test_add_rejects_empty_required_fields(self):
        for field in ("name", "path", "exe"):
            with self.subTest(field=field):
                kwargs = dict(name="N", path="P", exe="E")
                kwargs[field] = "   "
                with self.assertRaises(ValueError):
                    self.db.add(**kwargs)

    def test_duplicate_path_exe_rejected(self):
        self._add()
        with self.assertRaises(sqlite3.IntegrityError):
            self._add(name="另一个名字")

    def test_update(self):
        gid = self._add()
        self.assertTrue(self.db.update(gid, name="新名字", tags="RPG, 中文"))
        row = self.db.get(gid)
        self.assertEqual(row["name"], "新名字")
        self.assertEqual(row["tags"], "RPG,中文")

    def test_update_rejects_unknown_field(self):
        gid = self._add()
        with self.assertRaises(ValueError):
            self.db.update(gid, added_at="2020-01-01")

    def test_update_and_delete_missing_id(self):
        self.assertFalse(self.db.update(999999, name="x"))
        self.assertFalse(self.db.delete(999999))
        self.assertIsNone(self.db.get(999999))

    def test_delete(self):
        gid = self._add()
        self.assertTrue(self.db.delete(gid))
        self.assertIsNone(self.db.get(gid))
        self.assertFalse(self.db.delete(gid))

    def test_list_keyword_tag_and_order(self):
        self._add(name="Zelda", path=r"D:\Games\Z", exe="z.exe", tags="动作")
        self._add(name="Alpha", path=r"D:\Games\A", exe="a.exe", tags="独立, 动作")
        self._add(name="Beta", path=r"D:\Games\B", exe="b.exe",
                  note="动作游戏", tags="RPG")
        self.assertEqual(
            [r["name"] for r in self.db.list()], ["Alpha", "Beta", "Zelda"])
        self.assertEqual(
            [r["name"] for r in self.db.list(keyword="Alpha")], ["Alpha"])
        self.assertEqual(
            [r["name"] for r in self.db.list(keyword="动作")], ["Beta"])
        self.assertEqual(
            {r["name"] for r in self.db.list(tag="动作")}, {"Zelda", "Alpha"})

    def test_keyword_wildcards_are_literal(self):
        self._add(name="100% 完成", path=r"D:\Games\P", exe="p.exe")
        self._add(name="普通", path=r"D:\Games\N", exe="n.exe")
        self.assertEqual(
            [r["name"] for r in self.db.list(keyword="%")], ["100% 完成"])

    def test_data_persists_across_instances(self):
        gid = self._add()
        reopened = db.GameDB(self.db.db_path)
        self.assertEqual(reopened.get(gid)["name"], "测试游戏")


if __name__ == "__main__":
    unittest.main(verbosity=2)
