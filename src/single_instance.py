"""Windows 单实例：exe 已在运行时，第二次启动改为激活已有窗口并退出。

仅在打包后的 exe（frozen）启用；源码模式不做限制，便于开发时多开调试。
互斥量句柄保存在模块级变量，防止被 GC 关闭导致「已有实例」判定失效。
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from typing import Callable

WINDOW_TITLE = "本地游戏库管理器"
MUTEX_NAME = "Local\\GameManager_SingleInstance_v1"
ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9

_mutex_handle = None       # 必须全程保持引用，否则 mutex 会被销毁

_ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _default_kernel32():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k.CreateMutexW.restype = wintypes.HANDLE
    return k


def _default_user32():
    """返回配置好 argtypes 的 user32；ctypes 配置集中在此，便于注入假对象测试。"""
    u = ctypes.windll.user32
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.restype = ctypes.c_int
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.restype = ctypes.c_int
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsWindowVisible.restype = wintypes.BOOL
    u.EnumWindows.argtypes = [_ENUM_PROC, wintypes.LPARAM]
    u.EnumWindows.restype = wintypes.BOOL
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    return u


def find_window(user32, title: str = WINDOW_TITLE):
    """枚举顶层窗口，返回标题匹配且可见的句柄；找不到返回 None。"""
    found = []

    def cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if title in buf.value:
                    found.append(hwnd)
        return True

    user32.EnumWindows(_ENUM_PROC(cb), 0)
    return found[0] if found else None


def activate_window(user32, hwnd) -> None:
    """还原并置前已有窗口（最小化时先还原）。"""
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    # SetForegroundWindow 受 Windows 前台锁定限制，偶尔失败；用未文档化但长期
    # 稳定的 SwitchToThisWindow 兜底，强制把窗口切到前台。
    switch = getattr(user32, "SwitchToThisWindow", None)
    if switch is not None:
        switch(hwnd, True)


def acquire(*,
            enabled: bool | None = None,
            kernel32=None,
            user32=None,
            get_last_error: Callable[[], int] | None = None,
            window_finder: Callable[[], object] | None = None,
            sleeper: Callable[[float], None] | None = None,
            retries: int = 25,
            interval: float = 0.1,
            title: str = WINDOW_TITLE) -> bool:
    """返回 True=本进程应继续启动；False=已有实例（已尝试激活），调用方应退出。

    参数可注入，便于在任意平台做纯逻辑单测；默认走真实 Win32 API。
    """
    if enabled is None:
        enabled = sys.platform == "win32"
    if not enabled:
        return True

    if kernel32 is None:
        kernel32 = _default_kernel32()
    if get_last_error is None:
        get_last_error = ctypes.get_last_error

    global _mutex_handle
    _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if get_last_error() != ERROR_ALREADY_EXISTS:
        return True                      # 第一个实例：持有 mutex 继续启动

    # 已有实例：窗口可能还在创建中，短暂轮询等待，找到就激活
    if user32 is None:
        user32 = _default_user32()
    if window_finder is None:
        window_finder = lambda: find_window(user32, title)
    if sleeper is None:
        sleeper = time.sleep
    for _ in range(retries):
        hwnd = window_finder()
        if hwnd:
            activate_window(user32, hwnd)
            break
        sleeper(interval)
    return False                         # 无论如何都不再开第二个窗口
