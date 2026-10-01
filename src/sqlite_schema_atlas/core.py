"""Read schema only from closed trusted snapshots. Never open an input writable."""

import hashlib
from pathlib import Path
import re
import sqlite3


def snapshot(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Expected regular database up to 64 MiB")

    def sidecars():
        for suffix in ["-wal", "-journal"]:
            side = Path(str(p) + suffix)
            if side.exists() and side.stat().st_size:
                raise ValueError(
                    "Close/checkpoint database first; live sidecar detected"
                )

    sidecars()
    before = (p.stat().st_size, p.stat().st_mtime_ns)
    with p.open("rb") as f:
        if f.read(16) != b"SQLite format 3\x00":
            raise ValueError("SQLite header missing")
    con = None
    try:
        con = sqlite3.connect(p.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA trusted_schema=OFF")
        steps = [0]

        def progress():
            steps[0] += 1
            return int(steps[0] > 5000)

        con.set_progress_handler(progress, 1000)
        rows = con.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name LIMIT 2001"
        ).fetchall()
        if len(rows) > 2000:
            raise ValueError("Too many schema objects")
        objects, columns, foreign_keys = [], [], []
        for kind, name, table, sql in rows:
            if sql and len(sql) > 1024 * 1024:
                raise ValueError("Schema statement too large")
            virtual = bool(
                sql and re.match(r"\s*CREATE\s+VIRTUAL\s+TABLE\b", sql, re.I)
            )
            objects.append(
                {
                    "type": kind,
                    "name": name,
                    "table": table,
                    "ddl_sha256": hashlib.sha256((sql or "").encode()).hexdigest(),
                    "introspection": "skipped virtual table"
                    if virtual
                    else "schema only",
                }
            )
            if kind != "table" or virtual:
                continue
            quoted = '"' + name.replace('"', '""') + '"'
            for col in con.execute("PRAGMA table_xinfo(" + quoted + ")"):
                columns.append(
                    {
                        "table": name,
                        "column": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "has_default": col[4] is not None,
                        "primary_key_position": col[5],
                        "hidden": col[6],
                    }
                )
            for fk in con.execute("PRAGMA foreign_key_list(" + quoted + ")"):
                foreign_keys.append(
                    {
                        "table": name,
                        "id": fk[0],
                        "sequence": fk[1],
                        "target_table": fk[2],
                        "from_column": fk[3],
                        "to_column": fk[4],
                        "on_update": fk[5],
                        "on_delete": fk[6],
                    }
                )
            if len(columns) + len(foreign_keys) > 10000:
                raise ValueError("Schema detail limit")
        sidecars()
        if before != (p.stat().st_size, p.stat().st_mtime_ns):
            raise ValueError("Database changed during inspection")
        return {"objects": objects, "columns": columns, "foreign_keys": foreign_keys}
    except sqlite3.Error as exc:
        raise ValueError("Database could not be safely inspected") from exc
    finally:
        if con is not None:
            con.close()


def compare(a, b):
    left = {(x["type"], x["name"]): x for x in a["objects"]}
    right = {(x["type"], x["name"]): x for x in b["objects"]}
    return [
        {
            "type": key[0],
            "name": key[1],
            "change": "added"
            if key not in left
            else "removed"
            if key not in right
            else "ddl_changed",
        }
        for key in sorted(left.keys() | right.keys())
        if left.get(key) != right.get(key)
    ]


def configure(parser):
    parser.add_argument("database", nargs="?")
    parser.add_argument("--before", help="Optional prior closed database snapshot")


def run(args):
    if not args.database:
        raise ValueError("Database required")
    current = snapshot(args.database)
    changes = compare(snapshot(args.before), current) if args.before else []
    return {
        **current,
        "changes": changes,
        "comparison_requested": bool(args.before),
        "finding_count": len(changes),
        "boundary": "No row data/default literals exported. DDL hashes can change for formatting alone. Zero changes is not migration safety. Virtual table introspection skipped; use closed trusted snapshots.",
    }


def demo():
    import tempfile
    import argparse

    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp, "before.db"), Path(tmp, "after.db")
        for path, ddl in [
            (a, "CREATE TABLE item(id INTEGER PRIMARY KEY, label TEXT);"),
            (
                b,
                "CREATE TABLE item(id INTEGER PRIMARY KEY, label TEXT, tag TEXT); CREATE TABLE note(id INTEGER PRIMARY KEY, item_id INTEGER REFERENCES item(id));",
            ),
        ]:
            con = sqlite3.connect(path)
            try:
                con.executescript(ddl)
                con.commit()
            finally:
                con.close()
        return run(argparse.Namespace(database=str(b), before=str(a)))
