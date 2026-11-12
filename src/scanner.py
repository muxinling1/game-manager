"""F2 游戏扫描器：只读目录条目，绝不执行任何文件。

扫描结果只是「候选」，由调用方（F3）让用户确认后才写入数据库。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

EXCLUDED_EXE_PARTS = (
    "unins", "uninstall", "setup", "redist", "vcredist", "dxsetup",
    "crash", "report", "update", "patcher", "eac_", "beservice",
    "dotnetfx", "oalinst", "physx", "xna",
)

EXCLUDED_DIRS = frozenset({
    "$recycle.bin", "system volume information", "windows", "programdata",
    "appdata", "node_modules", "__pycache__", ".git", ".svn",
    "commonredist", "_commonredist", "directx", "vcredist", "redist",
    "dotnet", "temp", "tmp", "cache", "crash", "logs", "drivers",
    "prerequisites", "installers",
})

# 这些目录名不适合当游戏名，向上再找一层
GENERIC_DIRS = frozenset({
    "bin", "binaries", "x64", "x86", "win64", "win32", "release",
    "debug", "system", "system32", "game", "runtime", "client", "server",
})


@dataclass(frozen=True)
class Candidate:
    name: str
    path: str   # exe 所在目录（绝对路径），同时作为启动时的 cwd
    exe: str    # exe 文件名

    @property
    def key(self) -> tuple[str, str]:
        return (self.path, self.exe)


def excluded_exe(filename: str) -> bool:
    stem = Path(filename).stem.lower()
    return any(part in stem for part in EXCLUDED_EXE_PARTS)


def excluded_dir(dirname: str) -> bool:
    return dirname.lower() in EXCLUDED_DIRS


def guess_name(exe_path: Path) -> str:
    current = exe_path.parent
    for _ in range(3):
        if current.name and current.name.lower() not in GENERIC_DIRS:
            return current.name
        if current.parent == current:
            break
        current = current.parent
    return exe_path.stem


def scan(root: str | Path, *, max_depth: int = 4) -> list[Candidate]:
    """扫描单个根目录，返回按名称排序的候选列表。

    max_depth 限制向下走的层数，也顺带把 Windows junction 循环限制在有限深度内。
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"不是有效目录: {root}")

    found: list[Candidate] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        depth = len(Path(dirpath).relative_to(root).parts)
        dirnames[:] = [
            d for d in dirnames
            if not excluded_dir(d) and depth + 1 <= max_depth
        ]
        for filename in filenames:
            if not filename.lower().endswith(".exe") or excluded_exe(filename):
                continue
            exe_path = Path(dirpath) / filename
            found.append(Candidate(
                name=guess_name(exe_path),
                path=str(exe_path.parent),
                exe=filename,
            ))
    return sorted(found, key=lambda c: (c.name.lower(), c.exe.lower()))


def dedupe(candidates: Iterable[Candidate]) -> list[Candidate]:
    seen: set[tuple[str, str]] = set()
    result = []
    for candidate in candidates:
        if candidate.key not in seen:
            seen.add(candidate.key)
            result.append(candidate)
    return result


def filter_existing(candidates: Iterable[Candidate],
                    existing_keys: Iterable[tuple[str, str]]) -> list[Candidate]:
    """去掉数据库里已有的 (path, exe)，避免重复入库。"""
    existing = set(existing_keys)
    return [c for c in candidates if c.key not in existing]


def scan_many(roots: Iterable[str | Path], *,
              max_depth: int = 4) -> list[Candidate]:
    found: list[Candidate] = []
    for root in roots:
        found.extend(scan(root, max_depth=max_depth))
    return dedupe(found)
