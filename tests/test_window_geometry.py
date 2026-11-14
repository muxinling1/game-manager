"""窗口几何：按显示器工作区适配尺寸并居中。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, webapp  # noqa: E402


class GeometryTests(unittest.TestCase):
    def test_no_area_keeps_defaults(self):
        self.assertEqual(webapp.geometry_for(None), {})

    def test_centers_on_various_resolutions(self):
        for area in [(0, 0, 1366, 728), (0, 0, 1920, 1040),
                     (0, 0, 2560, 1400), (0, 0, 1024, 728),
                     (100, 50, 1600, 900)]:
            g = webapp.geometry_for(area)
            left, top, avail_w, avail_h = area
            cx = g["x"] + g["width"] / 2
            cy = g["y"] + g["height"] / 2
            self.assertLessEqual(abs(cx - (left + avail_w / 2)), 1, area)
            self.assertLessEqual(abs(cy - (top + avail_h / 2)), 1, area)
            self.assertLessEqual(g["width"], avail_w, area)
            self.assertLessEqual(g["height"], avail_h, area)
            self.assertGreaterEqual(g["width"], g["min_size"][0], area)
            self.assertGreaterEqual(g["height"], g["min_size"][1], area)

    def test_larger_screen_gets_larger_window(self):
        small = webapp.geometry_for((0, 0, 1366, 728))
        large = webapp.geometry_for((0, 0, 2560, 1400))
        self.assertLess(small["width"], large["width"])
        self.assertLess(small["height"], large["height"])
        self.assertLessEqual(large["width"], webapp._MAX_W)
        self.assertLessEqual(large["height"], webapp._MAX_H)

    def test_min_size_never_exceeds_work_area(self):
        g = webapp.geometry_for((0, 0, 800, 600))
        self.assertLessEqual(g["min_size"][0], 800)
        self.assertLessEqual(g["min_size"][1], 600)
        self.assertLessEqual(g["width"], 800)
        self.assertLessEqual(g["height"], 600)


class CreateWindowGeometryTests(unittest.TestCase):
    def test_create_window_passes_geometry(self):
        captured = {}

        class FakeWebview:
            def create_window(self, title, **kwargs):
                captured["title"] = title
                captured.update(kwargs)
                return "fake-window"

        result = webapp.create_window(FakeWebview(), api.Bridge())
        self.assertEqual(result, "fake-window")
        self.assertEqual(captured["title"], "本地游戏库管理器")
        self.assertIn("width", captured)
        self.assertIn("height", captured)
        if webapp.work_area() is not None:
            expected = webapp.geometry_for(webapp.work_area())
            for key in ("width", "height", "x", "y", "min_size"):
                self.assertEqual(captured[key], expected[key], key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
