"""编辑表单「打开目录」按钮对应的桥接方法：只打开真实存在的目录。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, db  # noqa: E402


class OpenFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.game = self.root / "Game"
        self.game.mkdir()
        self.database = db.GameDB(self.root / "g.db")
        self.database.init()
        self.calls = []
        self.bridge = api.Bridge(
            self.database, folder_opener=lambda p: self.calls.append(p))
        self.gid = self.database.add(
            name="Demo", path=str(self.game), exe="demo.exe")

    def tearDown(self):
        self.tmp.cleanup()

    def test_opens_existing_directory(self):
        res = self.bridge.open_folder(str(self.game))
        self.assertTrue(res["ok"], res)
        self.assertEqual(self.calls, [str(self.game)])

    def test_trims_surrounding_whitespace(self):
        res = self.bridge.open_folder("  " + str(self.game) + "  ")
        self.assertTrue(res["ok"], res)
        self.assertEqual(self.calls, [str(self.game)])

    def test_rejects_missing_directory(self):
        res = self.bridge.open_folder(str(self.root / "nope"))
        self.assertFalse(res["ok"])
        self.assertIn("目录", res["error"])
        self.assertEqual(self.calls, [])          # 未调用 opener

    def test_rejects_empty_path(self):
        for value in ("", "   ", None):
            self.assertFalse(self.bridge.open_folder(value)["ok"])
        self.assertEqual(self.calls, [])

    def test_rejects_file_instead_of_directory(self):
        f = self.root / "a.txt"
        f.write_text("x")
        res = self.bridge.open_folder(str(f))
        self.assertFalse(res["ok"])
        self.assertEqual(self.calls, [])

    def test_accepts_real_db_path(self):
        row = self.database.get(self.gid)
        self.assertTrue(self.bridge.open_folder(row["path"])["ok"])
        self.assertEqual(self.calls, [str(self.game)])

    def test_opener_error_is_reported(self):
        def boom(_path):
            raise OSError("denied")
        b = api.Bridge(self.database, folder_opener=boom)
        res = b.open_folder(str(self.game))
        self.assertFalse(res["ok"])
        self.assertIn("无法打开目录", res["error"])

    def test_is_read_only_does_not_execute_files(self):
        # 目标是目录， opener 可注入，不启动任何进程、不改数据库
        before = self.database.get(self.gid)
        self.bridge.open_folder(str(self.game))
        after = self.database.get(self.gid)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
