"""统一路径解析：兼容源码运行与 PyInstaller onefile 打包。

onefile 模式下 ``__file__`` 指向临时解压目录（每次启动都变），
所以「只读资源」和「可写数据」必须分开：
  - 资源（web/index.html、assets/app.ico）从 sys._MEIPASS 读；
  - 数据（games.db）写到持久目录，源码启动与 exe 启动共用同一份。
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """只读资源根目录。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """可写数据根目录（用户数据必须持久）。

    源码启动与 exe 启动共用同一个 games.db，避免两条路线数据分裂：
    exe 位于 <项目根>/dist 时，数据落在项目根；exe 被单独拷到别处时，
    改为落在 exe 旁边，保持可移植。
    """
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        project = exe_dir.parent
        if (project / "web" / "index.html").is_file() or (project / ".git").exists():
            return project
        return exe_dir
    return Path(__file__).resolve().parent.parent
