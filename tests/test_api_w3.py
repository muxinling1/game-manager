"""W3 桥接层测试：增删改与扫描导入，全部基于临时库与临时目录。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, db  # noqa: E402


class WriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bridge = api.Bridge(db.GameDB(Path(self.tmp.name) / "games.db"))
        self.bridge.init()

    def test_add_game(self):
        res = self.bridge.add_game({
            "name": "Demo", "path": "D:/Games/Demo", "exe": "demo.exe",
            "tags": "动作, 独立"})
        self.assertTrue(res["ok"], res)
        row = self.bridge.get_game(res["id"])
        self.assertEqual(row["name"], "Demo")
        self.assertEqual(row["tags"], "动作,独立")

    def test_add_game_rejects_empty_required(self):
        res = self.bridge.add_game({"name": "", "path": "P", "exe": "e.exe"})
        self.assertFalse(res["ok"])
        self.assertIn("不能为空", res["error"])

    def test_add_game_rejects_duplicate(self):
        fields = {"name": "A", "path": "D:/Games/A", "exe": "a.exe"}
        self.assertTrue(self.bridge.add_game(fields)["ok"])
        duplicate = self.bridge.add_game({**fields, "name": "B"})
        self.assertFalse(duplicate["ok"])

    def test_add_game_ignores_extra_fields(self):
        res = self.bridge.add_game({
            "name": "A", "path": "P", "exe": "e.exe", "id": 999,
            "play_count": 42, "bogus": "x"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(self.bridge.get_game(res["id"])["play_count"], 0)

    def test_update_game(self):
        gid = self.bridge.add_game(
            {"name": "A", "path": "P", "exe": "e.exe"})["id"]
        res = self.bridge.update_game(gid, {"name": "B", "tags": "RPG"})
        self.assertTrue(res["ok"], res)
        row = self.bridge.get_game(gid)
        self.assertEqual(row["name"], "B")
        self.assertEqual(row["tags"], "RPG")

    def test_update_missing_id(self):
        res = self.bridge.update_game(999999, {"name": "B"})
        self.assertFalse(res["ok"])

    def test_delete_game(self):
        gid = self.bridge.add_game(
            {"name": "A", "path": "P", "exe": "e.exe"})["id"]
        self.assertTrue(self.bridge.delete_game(gid)["ok"])
        self.assertIsNone(self.bridge.get_game(gid))
        self.assertFalse(self.bridge.delete_game(gid)["ok"])


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.picked: list[str] = []
        self.bridge = api.Bridge(
            db.GameDB(self.root / "games.db"),
            directory_picker=lambda: list(self.picked))
        self.bridge.init()

    def _make(self, rel):
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MZ")
        return target

    def test_pick_directories_uses_injected_picker(self):
        self.picked = [str(self.root / "A"), str(self.root / "B")]
        self.assertEqual(self.bridge.pick_directories(),
                         [str(self.root / "A"), str(self.root / "B")])

    def test_scan_preview_requires_roots(self):
        res = self.bridge.scan_preview([])
        self.assertFalse(res["ok"])
        self.assertEqual(res["candidates"], [])

    def test_scan_preview_returns_candidates_without_writing(self):
        self._make("Games/Alpha/alpha.exe")
        self._make("Games/Alpha/unins000.exe")
        self._make("Games/Beta/bin/beta.exe")
        res = self.bridge.scan_preview([str(self.root / "Games")])
        self.assertTrue(res["ok"], res)
        self.assertEqual([c["name"] for c in res["candidates"]],
                         ["Alpha", "Beta"])
        self.assertEqual(self.bridge.get_stats()["total"], 0)  # 只读，未入库

    def test_scan_preview_excludes_existing_and_reports_errors(self):
        self._make("Games/Alpha/alpha.exe")
        candidate = self.bridge.scan_preview([str(self.root / "Games")])
        self.bridge.import_games(candidate["candidates"])
        again = self.bridge.scan_preview(
            [str(self.root / "Games"), str(self.root / "NoSuchDir")])
        self.assertTrue(again["ok"])
        self.assertEqual(again["candidates"], [])   # 已入库的被过滤
        self.assertEqual(len(again["errors"]), 1)   # 无效目录单独报告

    def test_import_games_only_imports_submitted(self):
        self._make("Games/A/a.exe")
        self._make("Games/B/b.exe")
        candidates = self.bridge.scan_preview([str(self.root / "Games")])["candidates"]
        res = self.bridge.import_games(candidates[:1])
        self.assertEqual(res["imported"], 1)
        self.assertEqual(res["skipped"], 0)
        self.assertEqual(self.bridge.get_stats()["total"], 1)

    def test_import_games_skips_duplicates(self):
        self._make("Games/A/a.exe")
        candidates = self.bridge.scan_preview([str(self.root / "Games")])["candidates"]
        self.bridge.import_games(candidates)
        res = self.bridge.import_games(candidates)
        self.assertEqual(res["imported"], 0)
        self.assertEqual(res["skipped"], 1)

    def test_scan_to_import_end_to_end(self):
        self._make("Games/Alpha/alpha.exe")
        self._make("Games/Stardew/stardew.exe")
        res = self.bridge.scan_preview([str(self.root / "Games")])
        self.assertEqual(res["found"], 2)
        imported = self.bridge.import_games(res["candidates"])
        self.assertEqual(imported["imported"], 2)
        self.assertEqual(
            [r["name"] for r in self.bridge.list_games()], ["Alpha", "Stardew"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
