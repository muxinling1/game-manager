"""F3 启动器测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import launcher  # noqa: E402


class LauncherTests(unittest.TestCase):
    def test_split_args(self):
        self.assertEqual(launcher.split_args("-windowed -fps 60"),
                         ["-windowed", "-fps", "60"])
        self.assertEqual(launcher.split_args(""), [])
        self.assertEqual(launcher.split_args(None), [])

    def test_build_command(self):
        game = {"path": r"D:\Games\Demo", "exe": "demo.exe",
                "args": "-windowed -fps 60"}
        argv, cwd = launcher.build_command(game)
        self.assertEqual(argv, [str(Path(r"D:\Games\Demo") / "demo.exe"),
                                "-windowed", "-fps", "60"])
        self.assertEqual(cwd, r"D:\Games\Demo")

    def test_build_command_accepts_absolute_exe(self):
        game = {"path": r"D:\Games\Demo", "exe": r"C:\Other\demo.exe", "args": ""}
        argv, _ = launcher.build_command(game)
        self.assertEqual(argv[0], r"C:\Other\demo.exe")

    def test_launch_missing_exe_raises(self):
        game = {"path": r"D:\Games\Demo", "exe": "nope.exe", "args": ""}
        with self.assertRaises(FileNotFoundError):
            launcher.launch(game)

    def test_launch_real_process(self):
        exe = Path(sys.executable)
        game = {"path": str(exe.parent), "exe": exe.name, "args": "-c pass"}
        process = launcher.launch(game)
        self.assertEqual(process.wait(timeout=10), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
