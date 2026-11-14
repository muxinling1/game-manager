"""C2 封面：Pillow 缩略图、只读自动发现、桥接层 data URI。"""

from __future__ import annotations

import base64
import io
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import api, covers, db  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def png_bytes(size=(640, 960), color=(30, 80, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


@unittest.skipIf(Image is None, "Pillow 未安装")
class ThumbnailTests(unittest.TestCase):
    def test_output_is_webp_and_smaller_than_source(self):
        src = png_bytes()
        blob, mime = covers.make_thumbnail(src)
        self.assertEqual(mime, "image/webp")
        self.assertLess(len(blob), len(src))
        im = Image.open(io.BytesIO(blob))
        self.assertEqual(im.format, "WEBP")
        self.assertLessEqual(im.width, 300)
        self.assertLessEqual(im.height, 450)

    def test_keeps_aspect_ratio(self):
        blob, _ = covers.make_thumbnail(png_bytes((600, 400)))
        im = Image.open(io.BytesIO(blob))
        self.assertAlmostEqual(im.width / im.height, 1.5, delta=0.03)

    def test_transparent_png_keeps_alpha(self):
        buf = io.BytesIO()
        Image.new("RGBA", (100, 150), (10, 20, 30, 128)).save(buf, format="PNG")
        blob, _ = covers.make_thumbnail(buf.getvalue())
        self.assertIn("A", Image.open(io.BytesIO(blob)).getbands())

    def test_rejects_empty_and_non_image(self):
        with self.assertRaises(ValueError):
            covers.make_thumbnail(b"")
        with self.assertRaises(ValueError):
            covers.make_thumbnail(b"not an image")

    def test_data_uri_format(self):
        uri = covers.data_uri(b"abc", "image/webp")
        self.assertTrue(uri.startswith("data:image/webp;base64,"))
        self.assertEqual(base64.b64decode(uri.split(",", 1)[1]), b"abc")

    def test_ico_uses_largest_frame(self):
        buf = io.BytesIO()
        Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(
            buf, format="ICO", sizes=[(16, 16), (32, 32), (64, 64)])
        blob, mime = covers.make_thumbnail(buf.getvalue())
        self.assertEqual(mime, "image/webp")
        self.assertEqual(Image.open(io.BytesIO(blob)).width, 64)


class DiscoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Game"
        (self.root / "assets").mkdir(parents=True)
        for rel in ("cover.jpg", "poster.png", "random.png", "readme.txt",
                    "assets/banner.webp", "assets/texture.png"):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_images_and_skips_non_images(self):
        names = [Path(p).name for p in covers.discover_covers(self.root)]
        for expected in ("cover.jpg", "poster.png", "random.png",
                         "banner.webp", "texture.png"):
            self.assertIn(expected, names)
        self.assertNotIn("readme.txt", names)

    def test_root_cover_names_come_first(self):
        names = [Path(p).name for p in covers.discover_covers(self.root)]
        self.assertEqual(names[:2], ["cover.jpg", "poster.png"])

    def test_missing_directory_returns_empty(self):
        self.assertEqual(covers.discover_covers(self.root / "nope"), [])

    def test_does_not_modify_anything(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        covers.discover_covers(self.root)
        after = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


class BridgeCoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.database = db.GameDB(self.root / "g.db")
        self.database.init()
        self.bridge = api.Bridge(self.database)
        self.gid = self.database.add(
            name="Demo", path=str(self.root / "Game"), exe="demo.exe")

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skipIf(Image is None, "Pillow 未安装")
    def test_set_then_get_cover_as_data_uri(self):
        image = self.root / "cover.png"
        image.write_bytes(png_bytes())
        res = self.bridge.set_cover(self.gid, str(image))
        self.assertTrue(res["ok"], res)
        self.assertEqual(self.database.get_cover(self.gid)[1], "image/webp")

        got = self.bridge.get_cover(self.gid)
        self.assertTrue(got["ok"])
        self.assertTrue(got["uri"].startswith("data:image/webp;base64,"))
        self.assertEqual(base64.b64decode(got["uri"].split(",", 1)[1]),
                         self.database.get_cover(self.gid)[0])
        self.assertEqual(self.bridge.list_games()[0]["has_cover"], 1)

    def test_no_cover_and_clear(self):
        self.assertFalse(self.bridge.get_cover(self.gid)["ok"])
        self.assertEqual(self.bridge.list_games()[0]["has_cover"], 0)
        self.assertTrue(self.bridge.clear_cover(self.gid)["ok"])

    def test_rejects_missing_and_unsupported_file(self):
        self.assertFalse(self.bridge.set_cover(self.gid, "不存在.png")["ok"])
        txt = self.root / "a.txt"
        txt.write_text("x")
        self.assertFalse(self.bridge.set_cover(self.gid, str(txt))["ok"])

    def test_missing_game_id(self):
        self.assertFalse(self.bridge.get_cover(999999)["ok"])
        self.assertFalse(self.bridge.find_cover_candidates(999999)["ok"])
        self.assertFalse(self.bridge.set_cover(999999, "x.png")["ok"])

    def test_pick_image_file_opens_game_directory(self):
        game = self.root / "Game"
        game.mkdir(exist_ok=True)
        seen = []
        picked = api.Bridge(
            self.database,
            image_picker=lambda d: (seen.append(d), "D:/x/cover.png")[1])
        self.assertEqual(picked.pick_image_file(self.gid), "D:/x/cover.png")
        self.assertEqual(seen, [str(game)])   # 文件框初始目录 = 该游戏目录

    def test_pick_image_file_no_game_uses_empty_directory(self):
        seen = []
        b = api.Bridge(self.database,
                       image_picker=lambda d: (seen.append(d), None)[1])
        self.assertIsNone(b.pick_image_file(999999))
        self.assertEqual(seen, [""])

    def test_find_candidates_is_read_only(self):
        game = self.root / "Game"
        game.mkdir(exist_ok=True)
        (game / "cover.jpg").write_bytes(b"x")
        res = self.bridge.find_cover_candidates(self.gid)
        self.assertTrue(res["ok"])
        self.assertEqual([Path(p).name for p in res["paths"]], ["cover.jpg"])
        self.assertEqual(self.bridge.list_games()[0]["has_cover"], 0)

    def test_no_auto_exe_icon_apis(self):
        # 不再提供「自动匹配/一键使用 exe 图标」的方法，全由用户自己选
        self.assertFalse(hasattr(self.bridge, "use_exe_icon"))
        self.assertFalse(hasattr(covers, "find_exe_icon"))


@unittest.skipIf(Image is None, "Pillow 未安装")
class ManualIcoSelectionTests(unittest.TestCase):
    """用户自己在游戏目录里挑 .exe 同名 .ico，能正常生成封面。"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.game = self.root / "Game"
        self.game.mkdir()
        (self.game / "MyGame.exe").write_bytes(b"MZ")
        ico = io.BytesIO()
        Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(ico, format="ICO")
        (self.game / "MyGame.ico").write_bytes(ico.getvalue())
        self.database = db.GameDB(self.root / "g.db")
        self.database.init()
        self.bridge = api.Bridge(self.database)
        self.gid = self.database.add(name="MyGame", path=str(self.game),
                                     exe="MyGame.exe")

    def tearDown(self):
        self.tmp.cleanup()

    def test_candidates_include_ico_without_priority(self):
        # 候选里能看到 exe 同名 .ico，但不做任何自动置顶
        paths = self.bridge.find_cover_candidates(self.gid)["paths"]
        self.assertIn("MyGame.ico", [Path(p).name for p in paths])

    def test_user_picked_ico_becomes_cover(self):
        res = self.bridge.set_cover(self.gid, str(self.game / "MyGame.ico"))
        self.assertTrue(res["ok"], res)
        self.assertTrue(self.bridge.get_cover(self.gid)["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
