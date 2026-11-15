"""W4 桥接层测试：启动与运行状态回传，用假进程不真的启动游戏。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, db  # noqa: E402


class FakeProcess:
    """可控的假进程：poll() 按预设序列返回，terminate() 记录被停止。"""

    def __init__(self, codes):
        self.codes = list(codes)
        self.returncode = None
        self.terminated = False

    def poll(self):
        if self.codes:
            code = self.codes.pop(0)
            self.returncode = code
            return code
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self.codes = []
        return None


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.processes = []
        self.bridge = api.Bridge(
            db.GameDB(Path(self.tmp.name) / "games.db"),
            process_launcher=lambda game: self._spawn())
        self.bridge.init()

    def _spawn(self):
        proc = FakeProcess([None, 0])   # 第一次仍在运行，第二次已退出
        self.processes.append(proc)
        return proc

    def _add(self, name="Demo"):
        return self.bridge.add_game(
            {"name": name, "path": "D:/Games/Demo",
             "exe": f"{name}.exe"})["id"]

    def test_launch_records_play_and_marks_running(self):
        gid = self._add()
        res = self.bridge.launch_game(gid)
        self.assertTrue(res["ok"], res)
        row = self.bridge.get_game(gid)
        self.assertEqual(row["play_count"], 1)
        self.assertTrue(row["last_played"])
        st = self.bridge.poll_status()        # 第一次 poll：进程仍在运行
        self.assertEqual(st["running"], [gid])
        self.assertEqual(st["finished"], [])

    def test_poll_status_reports_finished(self):
        gid = self._add("Demo")
        self.bridge.launch_game(gid)
        self.bridge.poll_status()             # 第一次：None，仍在运行
        st = self.bridge.poll_status()        # 第二次：0，已退出
        self.assertEqual(st["running"], [])
        self.assertEqual(len(st["finished"]), 1)
        self.assertEqual(st["finished"][0]["name"], "Demo")
        self.assertEqual(st["finished"][0]["returncode"], 0)
        self.assertEqual(st["stats"]["launches"], 1)

    def test_finished_is_only_reported_once(self):
        gid = self._add()
        self.bridge.launch_game(gid)
        self.bridge.poll_status()
        self.assertEqual(len(self.bridge.poll_status()["finished"]), 1)
        self.assertEqual(self.bridge.poll_status()["finished"], [])

    def test_launch_missing_id(self):
        res = self.bridge.launch_game(999999)
        self.assertFalse(res["ok"])
        self.assertIn("不存在", res["error"])

    def test_launch_failure_is_reported_and_not_counted(self):
        def boom(_game):
            raise FileNotFoundError("找不到可执行文件: nope.exe")

        self.bridge.process_launcher = boom
        gid = self._add()
        res = self.bridge.launch_game(gid)
        self.assertFalse(res["ok"])
        self.assertIn("FileNotFoundError", res["error"])
        self.assertEqual(self.bridge.get_game(gid)["play_count"], 0)
        self.assertEqual(self.bridge.poll_status()["running"], [])

    def test_multiple_games_running_independently(self):
        a = self._add("Alpha")
        b = self._add("Beta")
        self.bridge.launch_game(a)
        self.bridge.launch_game(b)
        self.assertEqual(set(self.bridge.poll_status()["running"]), {a, b})
        self.assertEqual(self.bridge.get_stats()["launches"], 2)

    def test_nonzero_returncode_is_reported(self):
        self.bridge.process_launcher = lambda g: FakeProcess([3])
        gid = self._add()
        self.bridge.launch_game(gid)
        st = self.bridge.poll_status()
        self.assertEqual(st["finished"][0]["returncode"], 3)


class StopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.processes = []
        self.bridge = api.Bridge(
            db.GameDB(Path(self.tmp.name) / "games.db"),
            process_launcher=lambda game: self._spawn())
        self.bridge.init()

    def _spawn(self):
        proc = FakeProcess([None, None])   # 一直「运行中」，不会自然退出
        self.processes.append(proc)
        return proc

    def _add(self, name="Demo"):
        return self.bridge.add_game(
            {"name": name, "path": "D:/Games/Demo",
             "exe": f"{name}.exe"})["id"]

    def test_stop_terminates_process_and_removes_from_running(self):
        gid = self._add()
        self.bridge.launch_game(gid)
        self.assertEqual(self.bridge.poll_status()["running"], [gid])
        res = self.bridge.stop_game(gid)
        self.assertTrue(res["ok"] and res.get("stopped"), res)
        self.assertTrue(self.processes[0].terminated)
        self.assertEqual(self.bridge.poll_status()["running"], [])

    def test_stop_does_not_report_as_finished(self):
        # 主动停止不应被当作「异常退出」回传给前端
        gid = self._add()
        self.bridge.launch_game(gid)
        self.bridge.stop_game(gid)
        st = self.bridge.poll_status()
        self.assertEqual(st["finished"], [])

    def test_stop_when_not_running(self):
        res = self.bridge.stop_game(self._add())
        self.assertFalse(res["ok"])
        self.assertIn("未在运行", res["error"])

    def test_stop_twice_second_fails(self):
        gid = self._add()
        self.bridge.launch_game(gid)
        self.assertTrue(self.bridge.stop_game(gid)["ok"])
        self.assertFalse(self.bridge.stop_game(gid)["ok"])

    def test_stop_only_targets_one_game(self):
        a, b = self._add("Alpha"), self._add("Beta")
        self.bridge.launch_game(a)
        self.bridge.launch_game(b)
        self.bridge.stop_game(a)
        self.assertEqual(self.bridge.poll_status()["running"], [b])
        self.assertTrue(self.processes[0].terminated)
        self.assertFalse(self.processes[1].terminated)


if __name__ == "__main__":
    unittest.main(verbosity=2)
