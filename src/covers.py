"""封面处理：Pillow 生成 WebP 缩略图、只读发现游戏目录里的候选图片。

Pillow 在本模块内延迟导入，保证未安装时其它桥接方法仍可正常工作。
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

MAX_SOURCE_BYTES = 20 * 1024 * 1024      # 源图上限，避免超大文件
THUMB_SIZE = (300, 450)                  # 2:3，与卡片封面一致
WEBP_QUALITY = 82
OUTPUT_MIME = "image/webp"

IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".ico"})
COVER_KEYWORDS = ("cover", "poster", "banner", "folder", "boxart",
                  "header", "front", "library", "artwork")
MAX_CANDIDATES = 12


def make_thumbnail(data: bytes) -> tuple[bytes, str]:
    """把图片字节等比缩到 300×450 以内并输出 WebP，返回 (字节, MIME)。"""
    if not data:
        raise ValueError("图片为空")
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError(f"图片超过 {MAX_SOURCE_BYTES // 1048576} MB 上限")
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError("缺少 Pillow，请先运行 setup.bat") from exc
    try:
        with Image.open(io.BytesIO(data)) as src:
            src.seek(0)                  # GIF 等动图只取第一帧
            # 保留透明通道；不透明图用 RGB 省体积
            mode = "RGBA" if ("A" in src.getbands() or src.mode == "P") else "RGB"
            im = src.convert(mode)
            im = ImageOps.contain(im, THUMB_SIZE, Image.LANCZOS)
            out = io.BytesIO()
            im.save(out, format="WEBP", quality=WEBP_QUALITY, method=4)
    except UnidentifiedImageError as exc:
        raise ValueError("不是可识别的图片文件") from exc
    except OSError as exc:
        raise ValueError(f"图片读取失败: {exc}") from exc
    return out.getvalue(), OUTPUT_MIME


def data_uri(blob: bytes, mime: str) -> str:
    """把 BLOB 包成 <img> 可直接使用的 data URI。"""
    return f"data:{mime};base64,{base64.b64encode(blob).decode('ascii')}"


def _candidate_dirs(root: Path, max_depth: int):
    yield root
    if max_depth < 1:
        return
    try:
        children = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return
    for child in children:
        if child.is_dir() and not child.name.startswith("."):
            yield child


def discover_covers(game_dir: str | Path, *,
                    max_depth: int = 1) -> list[str]:
    """只读查找候选封面，按「文件名含封面关键词优先」排序返回绝对路径。

    全程只看目录条目和文件大小，不打开、不执行、不修改任何文件。
    """
    root = Path(game_dir)
    if not root.is_dir():
        return []
    hits: list[tuple[tuple[int, int], str]] = []
    for directory in _candidate_dirs(root, max_depth):
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        in_root = directory == root
        for p in entries:
            if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            stem = p.stem.lower()
            # 根目录优先，其次文件名含封面关键词
            rank = (0 if in_root else 1,
                    0 if any(k in stem for k in COVER_KEYWORDS) else 1)
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if not 0 < size <= MAX_SOURCE_BYTES:
                continue
            hits.append((rank, str(p.resolve())))
    hits.sort(key=lambda item: (item[0], item[1].lower()))
    return [path for _, path in hits[:MAX_CANDIDATES]]
