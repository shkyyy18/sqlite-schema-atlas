import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import unittest
import tempfile
import json
from sqlite_schema_atlas import core
import sqlite3
import hashlib


class SQLiteTests(unittest.TestCase):
    def make(self, path, sql):
        con = sqlite3.connect(path)
        try:
            con.executescript(sql)
            con.commit()
        finally:
            con.close()

    def test_read_only_no_row_export(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "db.sqlite")
            self.make(
                p,
                "CREATE TABLE a(id INTEGER PRIMARY KEY, text TEXT DEFAULT 'DEFAULT_PRIVATE'); INSERT INTO a(text) VALUES('ROW_PRIVATE');",
            )
            before = p.read_bytes()
            r = core.snapshot(p)
            self.assertEqual(before, p.read_bytes())
            self.assertNotIn("ROW_PRIVATE", json.dumps(r))
            self.assertNotIn("DEFAULT_PRIVATE", json.dumps(r))
            self.assertTrue(r["columns"][1]["has_default"])

    def test_foreign_keys(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "db")
            self.make(
                p,
                "CREATE TABLE a(id INTEGER PRIMARY KEY); CREATE TABLE b(a_id REFERENCES a(id));",
            )
            self.assertEqual(core.snapshot(p)["foreign_keys"][0]["target_table"], "a")

    def test_compare(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t, "a"), Path(t, "b")
            self.make(a, "CREATE TABLE a(x);")
            self.make(b, "CREATE TABLE a(x,y);CREATE TABLE b(z);")
            changes = core.compare(core.snapshot(a), core.snapshot(b))
            self.assertEqual({c["change"] for c in changes}, {"added", "ddl_changed"})

    def test_identical(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "a")
            self.make(p, "CREATE TABLE a(x);")
            r = core.snapshot(p)
            self.assertEqual(core.compare(r, r), [])

    def test_quoted_identifier(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "db")
            self.make(p, 'CREATE TABLE "a""b"("x" TEXT);')
            self.assertEqual(core.snapshot(p)["columns"][0]["table"], 'a"b')

    def test_reject_wal_or_journal(self):
        with tempfile.TemporaryDirectory() as t:
            for suffix in ["-wal", "-journal"]:
                p = Path(t, "a" + suffix.replace("-", ""))
                self.make(p, "CREATE TABLE a(x);")
                Path(str(p) + suffix).write_bytes(b"pending")
                with self.assertRaises(ValueError):
                    core.snapshot(p)

    def test_corrupt(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "bad")
            p.write_bytes(b"not sqlite")
            with self.assertRaises(ValueError):
                core.snapshot(p)

    def test_missing_not_created(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "absent")
            with self.assertRaises(ValueError):
                core.snapshot(p)
            self.assertFalse(p.exists())

    def test_views_not_executed(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "db")
            self.make(
                p,
                "CREATE TABLE a(x);CREATE VIEW danger AS SELECT unknown_function(x) FROM a;",
            )
            self.assertTrue(
                any(o["type"] == "view" for o in core.snapshot(p)["objects"])
            )

    def test_virtual_not_introspected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "db")
            try:
                self.make(p, "CREATE VIRTUAL TABLE search USING fts5(content);")
            except sqlite3.OperationalError:
                self.skipTest("FTS5 unavailable")
            r = core.snapshot(p)
            self.assertEqual(
                next(o for o in r["objects"] if o["name"] == "search")["introspection"],
                "skipped virtual table",
            )
            self.assertFalse(any(c["table"] == "search" for c in r["columns"]))
