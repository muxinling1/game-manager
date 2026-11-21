"""表单改为「可执行文件路径」：后端拆分路径 + 文件选择框可注入。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, db  # noqa: E402


class ExePathSplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = db.GameDB(Path(self.tmp.name) / "g.db")
        self.database.init()
        self.bridge = api.Bridge(self.database)

    def test_add_from_full_backslash_path(self):
        res = self.bridge.add_game({
            "name": "Demo", "exe": r"D:\Games\Demo\demo.exe"})
        self.assertTrue(res["ok"], res)
        row = self.database.get(res["id"])
        self.assertEqual(row["path"], r"D:\Games\Demo")
        self.assertEqual(row["exe"], "demo.exe")

    def test_add_from_full_slash_path(self):
        res = self.bridge.add_game({
            "name": "Demo", "exe": "D:/Games/Demo/demo.exe"})
        row = self.database.get(res["id"])
        self.assertEqual(row["path"], "D:\\Games\\Demo")
        self.assertEqual(row["exe"], "demo.exe")

    def test_add_from_root_drive_path(self):
        res = self.bridge.add_game({"name": "Demo", "exe": r"D:\demo.exe"})
        row = self.database.get(res["id"])
        self.assertEqual(row["path"], "D:\\")
        self.assertEqual(row["exe"], "demo.exe")

    def test_legacy_separate_path_exe_unchanged(self):
        # 未传完整路径时保持旧行为（扫描导入/旧调用方）
        res = self.bridge.add_game({
            "name": "Demo", "path": r"D:\Games\Demo", "exe": "demo.exe"})
        row = self.database.get(res["id"])
        self.assertEqual(row["path"], r"D:\Games\Demo")
        self.assertEqual(row["exe"], "demo.exe")

    def test_update_from_full_path(self):
        gid = self.bridge.add_game({
            "name": "Demo", "exe": r"D:\Games\Demo\demo.exe"})["id"]
        res = self.bridge.update_game(gid, {
            "name": "Demo2", "exe": r"E:\New\game.exe",
            "args": "", "tags": "", "note": ""})
        self.assertTrue(res["ok"], res)
        row = self.database.get(gid)
        self.assertEqual(row["path"], "E:\\New")
        self.assertEqual(row["exe"], "game.exe")
        self.assertEqual(row["name"], "Demo2")

    def test_missing_exe_is_rejected(self):
        res = self.bridge.add_game({"name": "Demo", "exe": ""})
        self.assertFalse(res["ok"])          # path 为空，db 拒绝


class ExePickerTests(unittest.TestCase):
    def test_pick_executable_is_injectable(self):
        b = api.Bridge(exe_picker=lambda: r"D:\Games\Demo\demo.exe")
        self.assertEqual(b.pick_executable(), r"D:\Games\Demo\demo.exe")
        cancelled = api.Bridge(exe_picker=lambda: None)
        self.assertIsNone(cancelled.pick_executable())

    def test_picker_result_round_trips_into_db(self):
        picked = r"D:\Games\Demo\demo.exe"
        b = api.Bridge(db.GameDB(Path(tempfile.mkdtemp()) / "g.db"),
                       exe_picker=lambda: picked)
        b.init()
        path = b.pick_executable()
        gid = b.add_game({"name": "Demo", "exe": path})["id"]
        row = b.database.get(gid)
        self.assertEqual(row["path"], r"D:\Games\Demo")
        self.assertEqual(row["exe"], "demo.exe")


if __name__ == "__main__":
    unittest.main(verbosity=2)
