"""PyInstaller 打包入口（只被 build_exe.bat 使用，不参与源码启动）。

源码启动仍是 ``python -m src.webapp``；这个入口让 PyInstaller 有一个
明确的顶层脚本，同时把 exe 所在目录加进 sys.path 以便 import src.*。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.webapp import main  # noqa: E402

if __name__ == "__main__":
    main()
