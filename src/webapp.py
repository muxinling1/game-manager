"""C2 入口：pywebview 窗口，直接加载本地 HTML，不启动 HTTP 服务。

运行：python -m src.webapp
依赖由 setup.bat 装进 ./vendor，未安装时这里会给出明确提示。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
INDEX = ROOT / "web" / "index.html"


def ensure_vendor_on_path() -> bool:
    """把 vendor 注入 sys.path；返回它是否可用。"""
    if not (VENDOR / "webview" / "__init__.py").is_file():
        return False
    if str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    return True


def create_window(webview, bridge):
    """单独拆出来便于自动化验证（可传入伪造的 webview）。"""
    return webview.create_window(
        "本地游戏库管理器",
        url=str(INDEX),
        js_api=bridge,
        width=1120, height=720,
        min_size=(900, 560),
        background_color="#15181e",
    )


def main() -> None:
    if not ensure_vendor_on_path():
        raise SystemExit("依赖未安装：请先运行 setup.bat（仅需联网一次）")
    import webview  # noqa: E402  (延迟导入，保证未装依赖时也能给出提示)
    from src.api import Bridge  # noqa: E402

    create_window(webview, Bridge())
    webview.start()


if __name__ == "__main__":
    main()
