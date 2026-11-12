"""启动本地游戏。F3 提供最小启动，F4 在其上补状态与游玩记录。"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def split_args(text: str | None) -> list[str]:
    """把启动参数按空白切分；MVP 不支持带空格的引号参数值。"""
    return (text or "").split()


def build_command(game: dict[str, Any]) -> tuple[list[str], str]:
    """返回 (argv, cwd)。exe 用 path/exe 拼成绝对路径，不走 shell。"""
    game_dir = Path(game["path"])
    argv = [str(game_dir / game["exe"]), *split_args(game.get("args"))]
    return argv, str(game_dir)


def launch(game: dict[str, Any]) -> subprocess.Popen:
    argv, cwd = build_command(game)
    if not Path(argv[0]).is_file():
        raise FileNotFoundError(f"找不到可执行文件: {argv[0]}")
    if not Path(cwd).is_dir():
        raise NotADirectoryError(f"游戏目录不存在: {cwd}")
    return subprocess.Popen(argv, cwd=cwd, shell=False)
