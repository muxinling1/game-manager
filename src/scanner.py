"""F2 游戏扫描器：只读目录条目，绝不执行任何文件。

扫描结果只是「候选」，由调用方（F3）让用户确认后才写入数据库。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

EXCLUDED_EXE_PARTS = (
    # 安装 / 卸载 / 运行时组件：绝不可能是游戏主程序，直接不扫描
    "unins", "uninstall", "setup", "redist", "vcredist", "dxsetup",
    "crash", "report", "update", "patcher", "eac_", "beservice",
    "dotnetfx", "oalinst", "physx", "xna", "bugsplat", "sndrpt",
    "crashpad", "dxwebsetup", "vc_redist",
)

# 工具 / 测试 / 编辑器类：仍保留为候选，但打上 tool 标记，
# 前端默认隐藏、可展开，绝不因启发式误判而丢数据。
TOOL_EXE_PARTS = (
    "test", "benchmark", "burner", "diagnostic", "editor", "browser",
    "compiler", "decompress", "popen", "xdelta", "cpatch",
    "redownloadfixer", "addoninstaller", "installer", "helper", "loader",
    "inject", "capture", "mux", "viewer", "console", "config",
    "util", "service", "plugin", "resource", "webclient", "sub_import",
    "rsubimport", "usm_sub", "to_l4n_", "winrtutil", "apputil",
)

EXCLUDED_DIRS = frozenset({
    "$recycle.bin", "system volume information", "windows", "programdata",
    "appdata", "node_modules", "__pycache__", ".git", ".svn",
    "commonredist", "_commonredist", "directx", "vcredist", "redist",
    "dotnet", "temp", "tmp", "cache", "crash", "logs", "drivers",
    "prerequisites", "installers", "crashpad",
})

# 这些目录名不适合当游戏名，向上再找一层；补上常见组件目录，
# 避免出现 64bit / distribution 这类一堆同名候选。
GENERIC_DIRS = frozenset({
    "bin", "binaries", "x64", "x86", "win64", "win32", "release",
    "debug", "system", "system32", "game", "runtime", "client", "server",
    "64bit", "32bit", "bin64", "bin32", "x86_64", "distribution",
    "plugins", "obs-plugins", "tools", "tool", "launcher", "launcher-se",
    "r_sub_import", "engine", "content",
})


@dataclass(frozen=True)
class Candidate:
    name: str
    path: str   # exe 所在目录（绝对路径），同时作为启动时的 cwd
    exe: str    # exe 文件名

    @property
    def key(self) -> tuple[str, str]:
        return (self.path, self.exe)


@dataclass(frozen=True)
class GameGroup:
    """一个游戏目录（一级子目录）下的所有候选，以及推荐的主程序。"""
    name: str
    path: str
    candidates: tuple[Candidate, ...]
    recommended: Candidate | None


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _initials(text: str) -> str:
    return "".join(word[0] for word in re.findall(r"[a-z0-9]+", text.lower()))


def score_main(candidate: Candidate, group: str, root: Path) -> float:
    """给候选打分，越高越像该游戏的主程序。

    只用于「默认勾选」的建议，绝不用于删除——启发式一定会挑错，
    用户必须能看到并改选所有候选。
    """
    stem = _norm(Path(candidate.exe).stem)
    group_norm = _norm(group)
    initials = _initials(group)
    score = 0.0
    if stem == group_norm:
        score += 120
    elif stem == initials:
        score += 100
    elif stem and (stem in group_norm or group_norm in stem):
        score += 70
    elif stem and initials and initials.startswith(stem):
        score += 60
    elif stem and initials and stem.startswith(initials):
        score += 50
    try:
        size_mb = (Path(candidate.path) / candidate.exe).stat().st_size / 1048576
    except OSError:
        size_mb = 0
    score += min(size_mb, 200) * 0.25
    depth = len(Path(candidate.path).relative_to(root).parts)
    score += (3 - depth) * 12
    if is_tool_exe(candidate.exe):
        score -= 45
    return round(score, 1)


def group_candidates(root: Path,
                     candidates: Iterable[Candidate]) -> list[GameGroup]:
    """按一级子目录分组，每组给出推荐主程序。"""
    buckets: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        group = group_name(root, Path(candidate.path))
        buckets.setdefault(group, []).append(candidate)
    groups = []
    for name in sorted(buckets, key=str.lower):
        items = tuple(sorted(buckets[name], key=lambda c: c.exe.lower()))
        best = max(items, key=lambda c: score_main(c, name, root))
        groups.append(GameGroup(
            name=name,
            path=str(root / name),
            candidates=items,
            recommended=best,
        ))
    return groups


def excluded_exe(filename: str) -> bool:
    stem = Path(filename).stem.lower()
    return any(part in stem for part in EXCLUDED_EXE_PARTS)


def is_tool_exe(filename: str) -> bool:
    stem = Path(filename).stem.lower()
    return any(part in stem for part in TOOL_EXE_PARTS)


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


def group_name(root: Path, exe_dir: Path) -> str:
    """把候选归到所选根目录下的一级子目录（Steam common 下一个目录 = 一个游戏）。"""
    try:
        rel = exe_dir.relative_to(root)
    except ValueError:
        return exe_dir.name
    return rel.parts[0] if rel.parts else root.name


def scan(root: str | Path, *, max_depth: int = 2) -> list[Candidate]:
    """扫描单个根目录，返回按名称排序的候选列表。

    默认只向下走 2 层：Steam 游戏主程序基本都在游戏根目录或一层子目录里，
    再深的 bin/64bit、obs-plugins 等几乎全是工具组件。max_depth 也顺带把
    Windows junction 循环限制在有限深度内。
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
              max_depth: int = 2) -> list[Candidate]:
    found: list[Candidate] = []
    for root in roots:
        found.extend(scan(root, max_depth=max_depth))
    return dedupe(found)
