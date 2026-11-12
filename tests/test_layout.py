"""U2 三栏布局测试（用 withdraw 的窗口，不弹界面）。"""

from __future__ import annotations

import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import app as A, db, theme  # noqa: E402


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError:
            self.root = None
            return
        self.database = db.GameDB(Path(self.tmp.name) / "layout.db")
        self.database.init()
        self.a = A.GameManagerApp(self.root, self.database)

    def tearDown(self):
        if self.root is not None:
            self.root.destroy()

    def _require_display(self):
        if self.root is None:
            self.skipTest("当前会话无可用显示")

    def _visible_names(self):
        return [self.a.tree.item(iid, "values")[0]
                for iid in self.a.tree.get_children()]

    def _tag_button_texts(self):
        return [c.cget("text") for c in self.a.tag_frame.winfo_children()
                if isinstance(c, ttk.Button)]

    def test_three_column_structure_exists(self):
        self._require_display()
        for name in ("side", "tag_frame", "stat_box", "detail",
                     "detail_launch", "view_title", "stat_total", "stat_live"):
            self.assertTrue(hasattr(self.a, name), name)
        columns, rows = self.root.grid_size()
        self.assertGreaterEqual(columns, 2)
        self.assertGreaterEqual(rows, 3)
        self.assertEqual(self.root.cget("background"), theme.BG)

    def test_tag_buttons_reflect_database(self):
        self._require_display()
        self.assertIn("（暂无标签）",
                      [c.cget("text") for c in self.a.tag_frame.winfo_children()])
        self.database.add(name="A", path="P1", exe="a.exe", tags="动作, 独立")
        self.database.add(name="B", path="P2", exe="b.exe", tags="动作")
        self.a.refresh()
        texts = self._tag_button_texts()
        self.assertEqual(len(texts), 2)
        self.assertTrue(any("动作" in t and "2" in t for t in texts))
        self.assertTrue(any("独立" in t and "1" in t for t in texts))

    def test_filter_tag_toggles(self):
        self._require_display()
        self.database.add(name="Alpha", path="P1", exe="a.exe", tags="动作")
        self.database.add(name="Beta", path="P2", exe="b.exe", tags="独立")
        self.a.refresh()
        self.a._filter_tag("动作")
        self.assertEqual(self.a.tag.get(), "动作")
        self.assertEqual(self._visible_names(), ["Alpha"])
        self.a._filter_tag("动作")
        self.assertEqual(self.a.tag.get(), "")
        self.assertEqual(self._visible_names(), ["Alpha", "Beta"])

    def test_recent_view_sorts_played_first(self):
        self._require_display()
        self.database.add(name="Alpha", path="P1", exe="a.exe")
        beta = self.database.add(name="Beta", path="P2", exe="b.exe")
        self.database.record_play(beta)
        self.a.refresh()
        self.assertEqual(self._visible_names(), ["Alpha", "Beta"])
        self.a._set_view("recent")
        self.assertEqual(self.a.view_title.cget("text"), "最近游玩")
        self.assertEqual(self._visible_names(), ["Beta", "Alpha"])
        self.assertEqual(self.a.nav_recent.cget("style"), "NavOn.TButton")
        self.a._set_view("all")
        self.assertEqual(self._visible_names(), ["Alpha", "Beta"])
        self.assertEqual(self.a.nav_all.cget("style"), "NavOn.TButton")

    def test_detail_follows_selection(self):
        self._require_display()
        gid = self.database.add(name="Runner", path=r"D:\Games\R",
                                exe="r.exe", tags="动作")
        self.a.refresh()
        self.assertEqual(str(self.a.detail_launch.cget("state")), "disabled")
        for iid in self.a.tree.get_children():
            if self.a.row_ids[iid] == gid:
                self.a.tree.selection_set(iid)
                break
        self.root.update()
        self.assertEqual(self.a.detail_name.cget("text"), "Runner")
        self.assertEqual(str(self.a.detail_launch.cget("state")), "normal")
        self.a.tree.selection_remove(self.a.tree.selection())
        self.root.update()
        self.assertEqual(self.a.detail_name.cget("text"), "未选中游戏")

    def test_status_statistics_are_real(self):
        self._require_display()
        first = self.database.add(name="A", path="P1", exe="a.exe")
        self.database.add(name="B", path="P2", exe="b.exe")
        self.database.record_play(first)
        self.database.record_play(first)
        self.a.refresh()
        self.assertEqual(self.a.stat_lines["total"].cget("text"), "2")
        self.assertEqual(self.a.stat_lines["played"].cget("text"), "1")
        self.assertEqual(self.a.stat_lines["launches"].cget("text"), "2 次")
        self.assertEqual(self.a.stat_total.cget("text"), "共 2 款游戏")
        self.assertIn("无运行中的游戏", self.a.stat_live.cget("text"))

    def test_theme_survives_layout_change(self):
        self._require_display()
        style = ttk.Style(self.root)
        self.assertEqual(style.theme_use(), "clam")
        self.assertEqual(style.lookup("Treeview", "background"), theme.PANEL_2)
        self.assertEqual(self.a.side.cget("style"), "Panel.TFrame")
        self.assertEqual(self.a.detail.cget("style"), "Card.TFrame")


if __name__ == "__main__":
    unittest.main(verbosity=2)
