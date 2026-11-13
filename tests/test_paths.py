"""路径解析测试：资源/数据分离，且源码与 exe 两条启动路线共用同一份数据库。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import paths  # noqa: E402


class SourceModeTests(unittest.TestCase):
    def test_not_frozen_in_tests(self):
        self.assertFalse(paths.is_frozen())

    def test_bundle_and_data_are_project_root(self):
        self.assertEqual(paths.bundle_dir(), BASE)
        self.assertEqual(paths.data_dir(), BASE)

    def test_default_db_path_is_persistent(self):
        from src import db
        self.assertEqual(db.DEFAULT_DB_PATH, BASE / "games.db")


class FrozenModeTests(unittest.TestCase):
    """模拟 sys.frozen / sys._MEIPASS / sys.executable（exe 被拷到别处）。"""

    def setUp(self):
        self.meipass = Path("C:/Temp/_MEI123")
        self.exedir = Path("D:/Apps/GameManager")

    def _patch(self):
        return mock.patch.multiple(
            sys,
            frozen=True,
            _MEIPASS=str(self.meipass),
            executable=str(self.exedir / "app.exe"),
            create=True,
        )

    def test_is_frozen(self):
        with self._patch():
            self.assertTrue(paths.is_frozen())

    def test_bundle_dir_uses_meipass(self):
        with self._patch():
            self.assertEqual(paths.bundle_dir(), self.meipass)

    def test_data_dir_uses_exe_directory_when_copied_away(self):
        """拷到别处（父目录没有项目特征）时，数据跟着 exe 走。"""
        with self._patch():
            self.assertEqual(paths.data_dir(), self.exedir)

    def test_resources_and_data_are_different(self):
        """onefile 下资源在临时目录、数据在持久目录，绝不能混。"""
        with self._patch():
            self.assertNotEqual(paths.bundle_dir(), paths.data_dir())
            self.assertEqual(paths.bundle_dir() / "web" / "index.html",
                             self.meipass / "web" / "index.html")
            self.assertEqual(paths.data_dir() / "games.db",
                             self.exedir / "games.db")


class UnifiedDbTests(unittest.TestCase):
    """exe 位于 <项目根>/dist 时，必须与源码启动共用同一个 games.db。"""

    def _patch_exe_in_dist(self):
        return mock.patch.multiple(
            sys,
            frozen=True,
            _MEIPASS=str(Path("C:/Temp/_MEI123")),
            executable=str(BASE / "dist" / "本地游戏库管理器.exe"),
            create=True,
        )

    def test_exe_in_dist_uses_project_root(self):
        with self._patch_exe_in_dist():
            self.assertEqual(paths.data_dir(), BASE)

    def test_frozen_matches_source(self):
        with self._patch_exe_in_dist():
            frozen_dir = paths.data_dir()
        self.assertEqual(frozen_dir, paths.data_dir())

    def test_resources_still_come_from_meipass_when_unified(self):
        with self._patch_exe_in_dist():
            self.assertEqual(paths.bundle_dir(), Path("C:/Temp/_MEI123"))
            self.assertNotEqual(paths.bundle_dir(), paths.data_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)
