"""C1 数据层：封面 BLOB 存储、幂等迁移、列表不含 BLOB。"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import db  # noqa: E402


class CoverStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbfile = Path(self.tmp.name) / "g.db"
        self.database = db.GameDB(self.dbfile)
        self.database.init()

    def tearDown(self):
        self.tmp.cleanup()

    def _add(self, name="Demo"):
        return self.database.add(name=name, path="P/" + name,
                                 exe=name + ".exe")

    def test_new_db_has_cover_columns(self):
        con = sqlite3.connect(str(self.dbfile))
        cols = {r[1] for r in con.execute("PRAGMA table_info(games)")}
        con.close()
        self.assertIn("cover", cols)
        self.assertIn("cover_mime", cols)

    def test_init_is_idempotent(self):
        self.database.init()
        self.database.init()
        self.assertEqual(len(self.database.list()), 0)

    def test_old_db_is_migrated_without_losing_rows(self):
        """模拟 C1 之前的老库：没有封面列，但已有数据。"""
        con = sqlite3.connect(str(self.dbfile))
        con.execute("DROP TABLE games")
        con.execute("""CREATE TABLE games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, path TEXT NOT NULL, exe TEXT NOT NULL,
            args TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '', added_at TEXT NOT NULL,
            last_played TEXT, play_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(path, exe))""")
        con.execute("INSERT INTO games (name,path,exe,added_at,play_count) "
                    "VALUES ('老游戏','P','old.exe','2026-01-01',7)")
        con.commit()
        con.close()

        self.database.init()
        rows = self.database.list()
        self.assertEqual([r["name"] for r in rows], ["老游戏"])
        self.assertEqual(rows[0]["play_count"], 7)
        self.assertEqual(rows[0]["has_cover"], 0)
        cols = None
        con = sqlite3.connect(str(self.dbfile))
        cols = {r[1] for r in con.execute("PRAGMA table_info(games)")}
        con.close()
        self.assertIn("cover", cols)
        self.assertIn("cover_mime", cols)

    def test_set_and_get_cover_roundtrip(self):
        gid = self._add()
        blob = b"\x89PNG\r\n\x1a\n" + bytes(range(64))
        self.assertTrue(self.database.set_cover(gid, blob, "image/webp"))
        self.assertEqual(self.database.get_cover(gid), (blob, "image/webp"))

    def test_list_and_get_exclude_blob_but_report_has_cover(self):
        gid = self._add()
        self.database.set_cover(gid, b"cover-bytes", "image/webp")
        row = self.database.list()[0]
        self.assertNotIn("cover", row)
        self.assertNotIn("cover_mime", row)
        self.assertEqual(row["has_cover"], 1)
        detail = self.database.get(gid)
        self.assertNotIn("cover", detail)
        self.assertEqual(detail["has_cover"], 1)

    def test_no_cover_reports_zero(self):
        gid = self._add()
        self.assertIsNone(self.database.get_cover(gid))
        self.assertEqual(self.database.get(gid)["has_cover"], 0)

    def test_clear_cover(self):
        gid = self._add()
        self.database.set_cover(gid, b"bytes", "image/webp")
        self.assertTrue(self.database.clear_cover(gid))
        self.assertIsNone(self.database.get_cover(gid))
        self.assertEqual(self.database.get(gid)["has_cover"], 0)

    def test_empty_blob_clears_instead_of_storing(self):
        gid = self._add()
        self.database.set_cover(gid, b"bytes", "image/webp")
        self.assertTrue(self.database.set_cover(gid, b"", ""))
        self.assertIsNone(self.database.get_cover(gid))

    def test_missing_id_returns_false_or_none(self):
        self.assertIsNone(self.database.get_cover(999999))
        self.assertFalse(self.database.set_cover(999999, b"x", "image/webp"))
        self.assertFalse(self.database.clear_cover(999999))

    def test_update_still_rejects_cover_field(self):
        """封面必须走 set_cover（含 Pillow 缩略图），不能被通用 update 绕过。"""
        gid = self._add()
        with self.assertRaises(ValueError):
            self.database.update(gid, cover=b"raw")

    def test_delete_removes_cover(self):
        gid = self._add()
        self.database.set_cover(gid, b"bytes", "image/webp")
        self.assertTrue(self.database.delete(gid))
        self.assertIsNone(self.database.get_cover(gid))


if __name__ == "__main__":
    unittest.main(verbosity=2)
