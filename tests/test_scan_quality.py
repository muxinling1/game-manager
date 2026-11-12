"""扫描质量规则测试：工具项软标记、分组、主程序打分、默认深度。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, db, scanner  # noqa: E402


class ToolMarkTests(unittest.TestCase):
    def test_install_component_is_hard_excluded(self):
        self.assertTrue(scanner.excluded_exe("unins000.exe"))
        self.assertTrue(scanner.excluded_exe("BugSplatHD64.exe"))
        self.assertTrue(scanner.excluded_exe("BsSndRpt.exe"))
        self.assertTrue(scanner.excluded_exe("vcredist_x64.exe"))

    def test_tool_exe_is_only_marked_not_deleted(self):
        for name in ("EssenceEditor.exe", "obs-amf-test.exe",
                     "ResourceBrowser.exe", "GPUBurner.exe",
                     "diagnostics64.exe", "xdelta3.exe"):
            with self.subTest(name=name):
                self.assertTrue(scanner.is_tool_exe(name))
                self.assertFalse(scanner.excluded_exe(name))

    def test_real_game_exe_is_neither(self):
        for name in ("AOW4.exe", "left4dead2.exe", "hl.exe",
                     "StreetFighter6.exe", "Cities2.exe"):
            with self.subTest(name=name):
                self.assertFalse(scanner.excluded_exe(name))
                self.assertFalse(scanner.is_tool_exe(name))


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "Games"
        self.root.mkdir()

    def _make(self, rel, size=1024):
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MZ" + b"\0" * size)
        return target

    def test_group_name_uses_first_level_dir(self):
        exe_dir = self.root / "Left 4 Dead 2" / "bin"
        self.assertEqual(scanner.group_name(self.root, exe_dir), "Left 4 Dead 2")
        self.assertEqual(scanner.group_name(self.root, self.root), self.root.name)

    def test_generic_dir_names_are_fixed(self):
        self._make("OBS/bin/64bit/obs64.exe")
        self._make("Wallpaper/distribution/wallpaper64.exe")
        found = scanner.scan(self.root, max_depth=4)
        self.assertEqual({c.name for c in found}, {"OBS", "Wallpaper"})

    def test_default_depth_is_two(self):
        self._make("Game/bin/64bit/deep.exe")
        self._make("Game/game.exe")
        found = scanner.scan(self.root)
        self.assertEqual([c.exe for c in found], ["game.exe"])

    def test_score_prefers_name_match_over_tool(self):
        big_tool = self._make("Age of Wonders 4/ResourceED.exe", size=9000)
        main = self._make("Age of Wonders 4/AOW4.exe", size=100)
        group = "Age of Wonders 4"
        c_tool = scanner.Candidate(group, str(big_tool.parent), big_tool.name)
        c_main = scanner.Candidate(group, str(main.parent), main.name)
        self.assertGreater(scanner.score_main(c_main, group, self.root),
                           scanner.score_main(c_tool, group, self.root))

    def test_group_candidates_picks_one_recommended_per_game(self):
        self._make("Alpha/Alpha.exe")
        self._make("Alpha/AlphaEditor.exe")
        self._make("Beta/beta.exe")
        found = scanner.scan(self.root)
        groups = scanner.group_candidates(self.root, found)
        self.assertEqual([g.name for g in groups], ["Alpha", "Beta"])
        alpha = groups[0]
        self.assertEqual(len(alpha.candidates), 2)
        self.assertEqual(alpha.recommended.exe, "Alpha.exe")
        self.assertEqual(groups[1].recommended.exe, "beta.exe")

    def test_group_candidates_never_drops_a_candidate(self):
        for i in range(6):
            self._make(f"Game/tool{i}Editor.exe")
        self._make("Game/Game.exe")
        found = scanner.scan(self.root)
        groups = scanner.group_candidates(self.root, found)
        self.assertEqual(sum(len(g.candidates) for g in groups), len(found))


class ScanPreviewGroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "Games"
        self.root.mkdir()
        self.bridge = api.Bridge(db.GameDB(Path(self.tmp.name) / "games.db"))
        self.bridge.init()

    def _make(self, rel):
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MZ")
        return target

    def test_preview_returns_groups_and_flat_candidates(self):
        self._make("Alpha/Alpha.exe")
        self._make("Alpha/AlphaEditor.exe")
        self._make("Beta/beta.exe")
        res = self.bridge.scan_preview([str(self.root)])
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["candidates"]), 3)   # 扁平契约仍保留
        self.assertEqual([g["name"] for g in res["groups"]], ["Alpha", "Beta"])
        alpha = res["groups"][0]
        self.assertEqual(alpha["recommended"], "Alpha.exe")
        tools = [it for it in alpha["items"] if it["tool"]]
        self.assertEqual([it["exe"] for it in tools], ["AlphaEditor.exe"])
        self.assertEqual(self.bridge.get_stats()["total"], 0)  # 只读

    def test_max_depth_is_configurable(self):
        self._make("Game/bin/64bit/deep.exe")
        shallow = self.bridge.scan_preview([str(self.root)], max_depth=2)
        deep = self.bridge.scan_preview([str(self.root)], max_depth=4)
        self.assertEqual(shallow["found"], 0)
        self.assertEqual(deep["found"], 1)

    def test_import_still_only_takes_submitted_items(self):
        self._make("Alpha/Alpha.exe")
        self._make("Alpha/AlphaEditor.exe")
        res = self.bridge.scan_preview([str(self.root)])
        main = next(it for g in res["groups"] for it in g["items"]
                    if it["exe"] == "Alpha.exe")
        imported = self.bridge.import_games([main])
        self.assertEqual(imported["imported"], 1)
        self.assertEqual(self.bridge.get_stats()["total"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
