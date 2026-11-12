"""F2 扫描器测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import scanner  # noqa: E402


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "Games"
        self.root.mkdir()

    def _make(self, rel):
        """造一个占位文件；文件名带 .exe 也不会被扫描器执行。"""
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MZ")
        return target

    def test_finds_game_exes_and_skips_uninstallers(self):
        self._make("GameA/game.exe")
        self._make("GameA/unins000.exe")
        self._make("GameA/setup.exe")
        result = scanner.scan(self.root)
        self.assertEqual([c.exe for c in result], ["game.exe"])
        self.assertEqual(result[0].name, "GameA")
        self.assertEqual(result[0].path,
                         str((self.root / "GameA").resolve()))

    def test_excluded_dirs_are_pruned(self):
        self._make("GameB/game.exe")
        self._make("GameB/CommonRedist/tool2.exe")
        self._make("GameB/_CommonRedist/tool3.exe")
        self._make("GameB/logs/tool4.exe")
        result = scanner.scan(self.root)
        self.assertEqual([c.exe for c in result], ["game.exe"])

    def test_excluded_exe_patterns(self):
        for filename in ("unins001.exe", "setup.exe", "vcredist_x86.exe",
                         "CrashReporter.exe", "patcher.exe",
                         "game_updater.exe"):
            self._make(f"X/{filename}")
        self._make("X/real.exe")
        result = scanner.scan(self.root)
        self.assertEqual([c.exe for c in result], ["real.exe"])

    def test_generic_bin_dir_uses_grandparent_name(self):
        self._make("CoolGame/bin/start.exe")
        result = scanner.scan(self.root)
        self.assertEqual(result[0].name, "CoolGame")
        self.assertEqual(result[0].path,
                         str((self.root / "CoolGame" / "bin").resolve()))

    def test_non_exe_files_are_ignored(self):
        self._make("GameA/readme.txt")
        self._make("GameA/data/asset.bin")
        self.assertEqual(scanner.scan(self.root), [])

    def test_uppercase_extension(self):
        self._make("GameA/GAME.EXE")
        self.assertEqual([c.exe for c in scanner.scan(self.root)], ["GAME.EXE"])

    def test_max_depth_bounds_walk(self):
        self._make("Deep/L1/L2/L3/L4/L5/too_deep.exe")
        self._make("Shallow/ok.exe")
        self.assertEqual(
            [c.exe for c in scanner.scan(self.root, max_depth=2)], ["ok.exe"])

    def test_invalid_root_raises(self):
        with self.assertRaises(ValueError):
            scanner.scan(self.root / "nope")
        with self.assertRaises(ValueError):
            scanner.scan(self._make("afile.txt"))

    def test_scan_many_dedupes_overlapping_roots(self):
        self._make("GameA/game.exe")
        result = scanner.scan_many([self.root, self.root / "GameA"])
        self.assertEqual(len(result), 1)

    def test_filter_existing(self):
        self._make("GameA/game.exe")
        result = scanner.scan(self.root)
        keys = {(c.path, c.exe) for c in result}
        self.assertEqual(scanner.filter_existing(result, keys), [])
        self.assertEqual(len(scanner.filter_existing(result, set())), 1)

    def test_scan_does_not_execute_or_modify_anything(self):
        exe = self._make("GameA/game.exe")
        before = exe.read_bytes()
        scanner.scan(self.root)
        self.assertEqual(exe.read_bytes(), before)
        self.assertFalse((self.root / "GameA" / "side_effect.txt").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
