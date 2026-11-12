"""W1 骨架测试：依赖清单、桥接层、启动契约。不弹窗口、不需要 vendor。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, webapp  # noqa: E402


class BridgeTests(unittest.TestCase):
    def test_get_version(self):
        value = api.Bridge().get_version()
        self.assertTrue(value.startswith("Python "))
        self.assertRegex(value, r"Python \d+\.\d+\.\d+")

    def test_ping(self):
        self.assertEqual(api.Bridge().ping(), "pong")


class EntryTests(unittest.TestCase):
    def test_requirements_pins_pywebview(self):
        text = (BASE / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("pywebview==6.2.1", text)

    def test_create_window_contract_with_fake_webview(self):
        captured = {}

        class FakeWebview:
            def create_window(self, title, **kwargs):
                captured["title"] = title
                captured.update(kwargs)
                return "fake-window"

        result = webapp.create_window(FakeWebview(), api.Bridge())
        self.assertEqual(result, "fake-window")
        self.assertEqual(captured["title"], "本地游戏库管理器")
        self.assertEqual(Path(captured["url"]), BASE / "web" / "index.html")
        self.assertIsInstance(captured["js_api"], api.Bridge)
        self.assertEqual(captured["background_color"], "#15181e")

    def test_index_exists(self):
        self.assertTrue((BASE / "web" / "index.html").is_file())
        self.assertTrue(webapp.INDEX.is_file())

    def test_index_uses_pywebview_bridge(self):
        html = (BASE / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("pywebviewready", html)
        self.assertIn("pywebview.api", html)
        self.assertIn("get_version()", html)
        self.assertIn("ping()", html)

    def test_launcher_scripts_exist_and_keep_decision_3(self):
        run = (BASE / "run.bat").read_text(encoding="utf-8")
        setup = (BASE / "setup.bat").read_text(encoding="utf-8")
        self.assertIn("-m src.webapp", run)
        self.assertIn("vendor\\runtime.txt", run)
        self.assertIn("setup.bat", run)
        # 决策 3：先找系统 Python，再回退 DSH 内置运行时
        self.assertIn("where python", run)
        self.assertIn("dsh-runtimes", run)
        self.assertIn("--target vendor", setup)
        self.assertIn("runtime.txt", setup)

    def test_vendor_is_gitignored(self):
        text = (BASE / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("vendor/", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
