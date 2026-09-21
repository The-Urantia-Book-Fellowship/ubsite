"""Open the database and apply the schema."""

from __future__ import annotations

import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "build" / "schema"


def connect(path: pathlib.Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA synchronous = OFF")
    return con


def create(path: pathlib.Path) -> sqlite3.Connection:
    """Build from scratch into a .tmp, never in place."""
    if path.exists():
        path.unlink()
    con = connect(path)
    for f in sorted(SCHEMA.glob("*.sql")):
        con.executescript(f.read_text(encoding="utf-8"))
    return con
