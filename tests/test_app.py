"""F3 主窗口的纯逻辑测试；不创建任何窗口。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import app  # noqa: E402


class FormTests(unittest.TestCase):
    def test_validate_form_strips_values(self):
        result = app.validate_form({
            "name": "  游戏  ", "path": " D:/G ", "exe": " g.exe ",
            "args": "-windowed", "tags": "动作", "note": "备注",
        })
        self.assertEqual(result["name"], "游戏")
        self.assertEqual(result["path"], "D:/G")
        self.assertEqual(result["exe"], "g.exe")
        self.assertEqual(result["args"], "-windowed")

    def test_validate_form_fills_missing_optionals(self):
        result = app.validate_form({"name": "N", "path": "P", "exe": "E"})
        self.assertEqual(result["tags"], "")
        self.assertEqual(result["note"], "")
        self.assertEqual(result["args"], "")

    def test_validate_form_rejects_missing_required(self):
        for key in ("name", "path", "exe"):
            with self.subTest(key=key):
                values = {"name": "N", "path": "P", "exe": "E"}
                values[key] = "   "
                with self.assertRaises(ValueError):
                    app.validate_form(values)

    def test_row_values(self):
        row = {"name": "A", "tags": "x", "path": "P",
               "last_played": None, "play_count": 3}
        self.assertEqual(app.row_values(row), ("A", "x", "P", "-", "3"))
        row["last_played"] = "2026-11-12T00:00:00+00:00"
        self.assertEqual(app.row_values(row)[3], "2026-11-12T00:00:00+00:00")

    def test_existing_keys(self):
        rows = [{"path": "P", "exe": "a.exe"}, {"path": "P", "exe": "b.exe"}]
        self.assertEqual(app.existing_keys(rows),
                         {("P", "a.exe"), ("P", "b.exe")})

    def test_exit_text(self):
        self.assertEqual(app.exit_text("Demo", 0), "「Demo」正常退出")
        self.assertEqual(app.exit_text("Demo", 3), "「Demo」异常退出（返回码 3）")

    def test_state_column_declared(self):
        self.assertEqual(len(app.COLUMNS), 6)
        self.assertIn("state", app.COLUMNS)
        self.assertEqual(app.HEADERS["state"], "状态")
        self.assertIn("state", app.WIDTHS)

    def test_app_module_imports_without_opening_a_window(self):
        self.assertTrue(callable(app.main))
        self.assertTrue(callable(app.GameManagerApp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
