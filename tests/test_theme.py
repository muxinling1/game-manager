"""深色主题测试。"""

from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import theme  # noqa: E402


class ThemeTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError:
            self.root = None

    def tearDown(self):
        if self.root is not None:
            self.root.destroy()

    def _require_display(self):
        if self.root is None:
            self.skipTest("当前会话无可用显示")

    def test_all_color_tokens_are_hex(self):
        tokens = [value for key, value in vars(theme).items()
                  if key.isupper() and isinstance(value, str)]
        self.assertTrue(tokens)
        for value in tokens:
            self.assertRegex(value, r"^#[0-9a-fA-F]{6}$")

    def test_cover_color_is_stable_and_in_palette(self):
        first = theme.cover_color("ELDEN RING")
        self.assertEqual(first, theme.cover_color("ELDEN RING"))
        self.assertIn(first, theme.COVER_COLORS)
        self.assertEqual(len(set(theme.COVER_COLORS)), len(theme.COVER_COLORS))

    def test_apply_theme_sets_root_and_clam(self):
        self._require_display()
        theme.apply_theme(self.root)
        style = ttk.Style(self.root)
        self.assertEqual(self.root.cget("background"), theme.BG)
        self.assertEqual(style.theme_use(), "clam")
        self.assertEqual(style.lookup("Treeview", "background"), theme.PANEL_2)
        self.assertEqual(style.lookup("Treeview", "foreground"), theme.TEXT)
        self.assertEqual(style.lookup("Treeview.Heading", "background"),
                         theme.PANEL)
        self.assertEqual(style.lookup("TFrame", "background"), theme.BG)
        self.assertEqual(style.lookup("Accent.TButton", "background"),
                         theme.ACCENT)

    def test_treeview_rowheight_is_enlarged(self):
        self._require_display()
        theme.apply_theme(self.root)
        style = ttk.Style(self.root)
        self.assertEqual(int(style.lookup("Treeview", "rowheight")), 28)

    def test_tint_native_colors_listbox_and_toplevel(self):
        self._require_display()
        theme.apply_theme(self.root)
        top = tk.Toplevel(self.root)
        listbox = tk.Listbox(top)
        listbox.pack()
        theme.tint_native(self.root)
        self.assertEqual(listbox.cget("background"), theme.PANEL_2)
        self.assertEqual(listbox.cget("selectbackground"), theme.ACCENT)
        self.assertEqual(top.cget("background"), theme.BG)


if __name__ == "__main__":
    unittest.main(verbosity=2)
