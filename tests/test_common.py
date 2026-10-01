import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import unittest
import tempfile
import json
from sqlite_schema_atlas import core
from sqlite_schema_atlas.common import render, load_json, read_bytes


class CommonTests(unittest.TestCase):
    def test_html_escaping(self):
        report = render({"rows": [{"name": "<script>alert(1)</script>"}]}, "<img>")
        self.assertIn("&lt;script&gt;", report)
        self.assertNotIn("<script>alert", report)
        self.assertIn("connect-src 'none'", report)

    def test_json_duplicate(self):
        with self.assertRaises(ValueError):
            load_json('{"a":1,"a":2}')

    def test_json_nan(self):
        for value in ["NaN", "Infinity", "1e999"]:
            with self.assertRaises(ValueError):
                load_json(value)

    def test_file_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input"
            p.write_bytes(b"12345")
            with self.assertRaises(ValueError):
                read_bytes(p, 4)

    def test_demo_json(self):
        data = core.demo()
        self.assertIn("finding_count", data)
        json.dumps(data, allow_nan=False)

    def test_report_truncation(self):
        output = render({"rows": [{"i": x} for x in range(1001)]}, "test")
        self.assertIn("Preview limited to 1,000 rows", output)
