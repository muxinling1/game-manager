"""单实例逻辑：用注入的假 Win32 对象测试，不触碰真实系统/窗口。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import single_instance as si  # noqa: E402
from src import webapp  # noqa: E402


class FakeKernel32:
    def __init__(self, last_error=0):
        self.last_error = last_error
        self.created = []

    def CreateMutexW(self, _attrs, _owner, name):
        self.created.append(name)
        return object()          # 假句柄


class FakeUser32:
    def __init__(self):
        self.shown = []
        self.foreground = []
        self.switched = []

    def ShowWindow(self, hwnd, cmd):
        self.shown.append((hwnd, cmd))

    def SetForegroundWindow(self, hwnd):
        self.foreground.append(hwnd)

    def SwitchToThisWindow(self, hwnd, alt):
        self.switched.append((hwnd, alt))


class AcquireTests(unittest.TestCase):
    def test_non_windows_short_circuits(self):
        # enabled=False 时完全不碰 Win32，直接放行
        self.assertTrue(si.acquire(enabled=False))
        self.assertTrue(si.acquire(enabled=False, kernel32=None))

    def test_first_instance_keeps_running(self):
        k = FakeKernel32(last_error=0)
        self.assertTrue(si.acquire(enabled=True, kernel32=k,
                                  get_last_error=lambda: 0))
        self.assertEqual(k.created, [si.MUTEX_NAME])
        self.assertIsNotNone(si._mutex_handle)   # 句柄被持有，未被 GC

    def test_second_instance_activates_existing_window_and_exits(self):
        k = FakeKernel32(last_error=si.ERROR_ALREADY_EXISTS)
        u = FakeUser32()
        activated = []
        finder = lambda: 4242
        result = si.acquire(
            enabled=True, kernel32=k, user32=u,
            get_last_error=lambda: si.ERROR_ALREADY_EXISTS,
            window_finder=finder,
            sleeper=lambda _s: None,
            retries=3,
        )
        self.assertFalse(result)                  # 第二个实例应退出
        self.assertEqual(u.shown, [(4242, si.SW_RESTORE)])
        self.assertEqual(u.foreground, [4242])
        self.assertEqual(u.switched, [(4242, True)])

    def test_waits_for_window_that_appears_later(self):
        u = FakeUser32()
        seq = iter([None, None, 777])
        sleeps = []
        result = si.acquire(
            enabled=True, kernel32=FakeKernel32(),
            user32=u, get_last_error=lambda: si.ERROR_ALREADY_EXISTS,
            window_finder=lambda: next(seq),
            sleeper=lambda s: sleeps.append(s), retries=5,
        )
        self.assertFalse(result)
        self.assertEqual(u.foreground, [777])    # 第三次找到才激活
        self.assertEqual(len(sleeps), 2)         # 前两次等待

    def test_no_window_found_still_refuses_second_instance(self):
        u = FakeUser32()
        result = si.acquire(
            enabled=True, kernel32=FakeKernel32(), user32=u,
            get_last_error=lambda: si.ERROR_ALREADY_EXISTS,
            window_finder=lambda: None,
            sleeper=lambda _s: None, retries=4,
        )
        self.assertFalse(result)                  # 绝不新开窗口
        self.assertEqual(u.foreground, [])       # 没窗口可激活

    def test_mutex_handle_is_module_level(self):
        # 连续两次「第一个实例」不会覆盖成 None
        si.acquire(enabled=True, kernel32=FakeKernel32(),
                   get_last_error=lambda: 0)
        self.assertIsNotNone(si._mutex_handle)


class MainWiringTests(unittest.TestCase):
    """验证 main() 只在 frozen 时启用单实例，且第二实例不建窗口。"""

    def test_source_mode_does_not_acquire(self):
        with mock.patch.object(webapp.paths, "is_frozen", return_value=False), \
             mock.patch.object(webapp, "ensure_vendor_on_path", return_value=True), \
             mock.patch.object(si, "acquire") as acq, \
             mock.patch.object(webapp, "create_window") as cw, \
             mock.patch.dict(sys.modules, {"webview": mock.MagicMock()}), \
             mock.patch("src.api.Bridge"):
            webapp.main()
            acq.assert_not_called()              # 源码模式不启用
            self.assertTrue(cw.called)

    def test_frozen_second_instance_exits_before_window(self):
        with mock.patch.object(webapp.paths, "is_frozen", return_value=True), \
             mock.patch.object(si, "acquire", return_value=False), \
             mock.patch.object(webapp, "ensure_vendor_on_path") as ev, \
             mock.patch.object(webapp, "create_window") as cw:
            webapp.main()
            self.assertFalse(ev.called)          # 连依赖检查都不做
            cw.assert_not_called()               # 不建第二个窗口

    def test_frozen_first_instance_builds_window(self):
        with mock.patch.object(webapp.paths, "is_frozen", return_value=True), \
             mock.patch.object(si, "acquire", return_value=True), \
             mock.patch.object(webapp, "ensure_vendor_on_path", return_value=True), \
             mock.patch.object(webapp, "create_window") as cw, \
             mock.patch.dict(sys.modules, {"webview": mock.MagicMock()}), \
             mock.patch("src.api.Bridge"):
            webapp.main()
            self.assertTrue(cw.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
