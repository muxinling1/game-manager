"""汉字拼音匹配：把中文游戏名转成全拼 / 首字母，供搜索框前缀匹配。

拼音字典由 pypinyin 的公开数据离线提取，固化为纯文本（GB2312 常用字，
多音字取首个读音），运行时零第三方依赖。数据文件随代码进仓库。
"""

from __future__ import annotations

import json
from functools import lru_cache

from src import paths

_DATA = paths.bundle_dir() / "src" / "pinyin_data.json"


@lru_cache(maxsize=1)
def _table() -> dict[str, str]:
    with _DATA.open(encoding="utf-8") as fh:
        return json.load(fh)


def _keys(name: str) -> tuple[str, str]:
    """返回 (全拼串, 首字母串)；非汉字字符按小写原样保留。"""
    table = _table()
    full: list[str] = []
    initials: list[str] = []
    for ch in name:
        py = table.get(ch)
        if py:
            full.append(py)
            initials.append(py[0])
        else:
            full.append(ch.lower())
            initials.append(ch.lower())
    return "".join(full), "".join(initials)


@lru_cache(maxsize=4096)
def search_keys(name: str) -> tuple[str, str, str]:
    """一个名称的可搜索前缀键：原名、全拼、首字母缩写。"""
    full, initials = _keys(name)
    return name.casefold(), full, initials


def match(name: str, query: str) -> bool:
    """query 命中任一键的前缀即可（中文原名 / 全拼 / 首字母缩写）。"""
    q = query.strip().casefold()
    if not q:
        return True
    return any(key.startswith(q) for key in search_keys(name))
