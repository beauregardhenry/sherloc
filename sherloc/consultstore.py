"""Storage for the consultation answers (TAQ, scans, accounts, notes).

Each kind is one JSON document in the `consult_documents` table of the SQLite
database, next to the scan rows and app remarks. Earlier versions kept them as
JSON files in a folder; those files are moved into the database the first time
they are seen, and then overwritten and removed.
"""

import json
import os
import sqlite3

import config

TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS consult_documents ("
    " name TEXT PRIMARY KEY,"
    " body TEXT NOT NULL,"
    " updated_at DATETIME DEFAULT (datetime('now', 'localtime')))"
)

NAMES = ("taq", "scans", "accounts", "notes")


def db_path():
    return config.SQL_DB_PATH.replace("sqlite:///", "", 1).strip()


def _connect():
    path = db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, mode=0o700, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    # Replaced and deleted content is overwritten instead of left in free pages.
    con.execute("PRAGMA secure_delete = ON")
    con.execute(TABLE_SQL)
    return con


def _legacy_file(legacy_dir, name):
    return os.path.join(legacy_dir, name + ".json")


def _overwrite_and_remove(path):
    try:
        size = os.path.getsize(path)
        with open(path, "r+b") as f:
            f.write(b"\0" * size)
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass
    os.remove(path)


def _remove_if_exists(path):
    if os.path.exists(path):
        _overwrite_and_remove(path)


def _migrate(con, legacy_dir):
    """Move JSON files from an earlier version into the database."""
    if not legacy_dir:
        return
    for name in NAMES:
        fname = _legacy_file(legacy_dir, name)
        if not os.path.exists(fname):
            continue
        try:
            with open(fname, "r") as f:
                body = json.dumps(json.load(f))
        except (OSError, ValueError):
            continue  # leave a file we cannot read; do not lose it
        with con:
            # Answers already in the database are newer: never replace them.
            con.execute(
                "INSERT OR IGNORE INTO consult_documents (name, body) VALUES (?, ?)",
                (name, body),
            )
        _overwrite_and_remove(fname)
        _remove_if_exists(fname + ".lock")


def save(name, body, legacy_dir=None):
    con = _connect()
    try:
        _migrate(con, legacy_dir)
        with con:
            con.execute(
                "INSERT INTO consult_documents (name, body) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET body = excluded.body, "
                "updated_at = datetime('now', 'localtime')",
                (name, body),
            )
    finally:
        con.close()


def load(name, legacy_dir=None):
    """Return the stored JSON text, or None if nothing is stored."""
    con = _connect()
    try:
        _migrate(con, legacy_dir)
        row = con.execute(
            "SELECT body FROM consult_documents WHERE name = ?", (name,)
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def count(legacy_dir=None):
    """Number of stored documents plus old JSON files not yet moved."""
    n = 0
    path = db_path()
    if os.path.isfile(path):
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                n = con.execute("SELECT count(*) FROM consult_documents").fetchone()[0]
            finally:
                con.close()
        except sqlite3.Error:
            n = 0
    if legacy_dir:
        n += sum(1 for name in NAMES if os.path.exists(_legacy_file(legacy_dir, name)))
    return n


def discard_legacy_files(legacy_dir):
    """Overwrite and remove old JSON files (and lock files) without reading them."""
    if not legacy_dir:
        return
    for name in NAMES:
        fname = _legacy_file(legacy_dir, name)
        _remove_if_exists(fname)
        _remove_if_exists(fname + ".lock")
