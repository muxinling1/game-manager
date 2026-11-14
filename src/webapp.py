"""C2 入口：pywebview 窗口，直接加载本地 HTML，不启动 HTTP 服务。

运行：python -m src.webapp
依赖由 setup.bat 装进 ./vendor，未安装时这里会给出明确提示。
窗口按主显示器工作区适配尺寸并居中显示。
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from src import paths

BUNDLE = paths.bundle_dir()
VENDOR = BUNDLE / "vendor"
INDEX = BUNDLE / "web" / "index.html"
ICON = BUNDLE / "assets" / "app.ico"

# 窗口占工作区的比例与上下限（小屏不至于挤爆，大屏不至于铺满）
_RATIO_W, _RATIO_H = 0.78, 0.82
_MAX_W, _MAX_H = 1600, 1000
_MIN_W, _MIN_H = 900, 560


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def work_area() -> tuple[int, int, int, int] | None:
    """主显示器工作区 (left, top, width, height)；非 Windows 返回 None。

    用工作区而非整屏，避免窗口底部被任务栏遮住。
    """
    if sys.platform != "win32":
        return None
    rect = _RECT()
    try:
        # SPI_GETWORKAREA = 0x0030
        ok = ctypes.windll.user32.SystemParametersInfoW(
            0x0030, 0, ctypes.byref(rect), 0)
    except (AttributeError, OSError):
        return None
    if not ok:
        return None
    return (rect.left, rect.top,
            rect.right - rect.left, rect.bottom - rect.top)


def geometry_for(area: tuple[int, int, int, int] | None) -> dict:
    """按工作区计算窗口尺寸与居中坐标（纯函数，便于测试）。"""
    if area is None:
        return {}
    left, top, avail_w, avail_h = area
    min_w, min_h = min(_MIN_W, avail_w), min(_MIN_H, avail_h)
    width = min(max(min_w, min(_MAX_W, int(avail_w * _RATIO_W))), avail_w)
    height = min(max(min_h, min(_MAX_H, int(avail_h * _RATIO_H))), avail_h)
    return {
        "width": width,
        "height": height,
        "x": left + (avail_w - width) // 2,
        "y": top + (avail_h - height) // 2,
        "min_size": (min_w, min_h),
    }


def ensure_vendor_on_path() -> bool:
    """把 vendor 注入 sys.path；返回它是否可用。

    打包后依赖已由 PyInstaller 收进 exe，无需 vendor 目录。
    """
    if paths.is_frozen():
        return True
    if not (VENDOR / "webview" / "__init__.py").is_file():
        return False
    if str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    return True


def create_window(webview, bridge):
    """单独拆出来便于自动化验证（可传入伪造的 webview）。"""
    options = {"width": 1120, "height": 720, "min_size": (900, 560)}
    options.update(geometry_for(work_area()))
    return webview.create_window(
        "本地游戏库管理器",
        url=str(INDEX),
        js_api=bridge,
        background_color="#15181e",
        **options,
    )


def main() -> None:
    # 打包后的 exe 才做单实例：第二次运行激活已有窗口并退出，不再开新窗口。
    # 源码模式不限制，方便边改边多开调试。
    if paths.is_frozen():
        from src import single_instance
        if not single_instance.acquire():
            return
    if not ensure_vendor_on_path():
        raise SystemExit("依赖未安装：请先运行 setup.bat（仅需联网一次）")
    import webview  # noqa: E402  (延迟导入，保证未装依赖时也能给出提示)
    from src.api import Bridge  # noqa: E402

    bridge = Bridge()
    bridge.init()          # CREATE TABLE IF NOT EXISTS，可重复调用
    create_window(webview, bridge)
    # 窗口/任务栏图标；图标不存在时 pywebview 会自行回退到默认图标
    webview.start(icon=str(ICON) if ICON.is_file() else None)


if __name__ == "__main__":
    main()
