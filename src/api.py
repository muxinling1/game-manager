"""C2 桥接层：这些方法会暴露给前端，成为 ``window.pywebview.api``。

W1 只有探针方法；W2 起逐步接入 db / scanner / launcher，前端不需要 HTTP 服务。
"""

from __future__ import annotations

import platform


class Bridge:
    def get_version(self) -> str:
        """前端用来确认 Python 桥接是否打通。"""
        return f"Python {platform.python_version()}"

    def ping(self) -> str:
        """前端用来做一次往返调用。"""
        return "pong"
