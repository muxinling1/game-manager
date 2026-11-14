"""拼音搜索的回归测试：中文原名 / 全拼 / 首字母缩写三种前缀匹配。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import db, pinyin  # noqa: E402


class PinyinDataTests(unittest.TestCase):
    def test_table_covers_common_chinese(self):
        table = pinyin._table()
        self.assertGreater(len(table), 6000)
        for ch, py in (("逃", "tao"), ("离", "li"), ("塔", "ta"),
                       ("科", "ke"), ("夫", "fu"), ("模", "mo")):
            self.assertEqual(table[ch], py)

    def test_search_keys(self):
        keys = pinyin.search_keys("逃离塔科夫")
        self.assertEqual(keys[0], "逃离塔科夫")
        self.assertTrue(keys[1].startswith("taoli"))
        self.assertTrue(keys[2].startswith("tltkf"))

    def test_match_variants(self):
        name = "逃离塔科夫"
        for q in ("逃", "tao", "taoli", "taolitakefu", "t", "tlt", "tltkf"):
            self.assertTrue(pinyin.match(name, q), q)
        for q in ("xyz", "life", "fu"):
            self.assertFalse(pinyin.match(name, q), q)


class DbPinyinSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.database = db.GameDB(Path(self.tmp.name) / "g.db")
        self.database.init()

    def tearDown(self):
        self.tmp.cleanup()

    def _add(self, name):
        return self.database.add(name=name, path="P/" + name,
                                 exe=name + ".exe")

    def names(self, keyword):
        return [r["name"] for r in self.database.list(keyword=keyword)]

    def test_chinese_name_matches_full_pinyin_and_initials(self):
        self._add("逃离塔科夫")
        self._add("模拟经营")
        self._add("Half-Life")
        self.assertEqual(self.names("tao"), ["逃离塔科夫"])
        self.assertEqual(self.names("taolitakefu"), ["逃离塔科夫"])
        self.assertEqual(self.names("tltkf"), ["逃离塔科夫"])
        self.assertEqual(self.names("mnjy"), ["模拟经营"])
        self.assertEqual(self.names("逃"), ["逃离塔科夫"])
        self.assertEqual(self.names("Half"), ["Half-Life"])
        self.assertEqual(self.names("xyz"), [])

    def test_english_prefix_still_works(self):
        self._add("Alpha")
        self._add("Half-Life")
        self.assertEqual(self.names("a"), ["Alpha"])
        self.assertEqual(self.names("life"), [])

    def test_tag_and_keyword_compose(self):
        self._add("逃离塔科夫")
        self.database.update(1, tags="第一人称射击")
        self.assertEqual([r["name"] for r in self.database.list(
            keyword="tao", tag="第一")], ["逃离塔科夫"])
        self.assertEqual(self.database.list(keyword="tao", tag="动作"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
