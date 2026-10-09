"""What client data is stored on this computer right now.

Used to tell the consultant, on every page, that data is stored and where to
remove it.
"""

import sqlite3
from pathlib import Path

import config

# (label, table) pairs counted in the database.
_TABLES = [
    ("Client notes in the database", "clients_notes"),
    ("Device scans in the database", "scan_res"),
    ("App remarks in the database", "app_info"),
]


def _count_files(directory, skip=()):
    d = Path(directory)
    if not d.is_dir():
        return 0
    return sum(
        1
        for f in d.rglob("*")
        if f.is_file() and not f.name.endswith(tuple(skip))
    )


def _count_rows(table):
    path = config.SQL_DB_PATH.replace("sqlite:///", "")
    if not Path(path).is_file():
        return 0
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return con.execute(f"select count(*) from {table}").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return 0


def summary():
    """Return `{"present": bool, "items": [(label, count), ...]}`.

    Only kinds with at least one item are listed.
    """
    counts = [
        ("Saved consultation answers", _count_files(config.CONSULT_DATA_DIR, skip=(".lock",))),
        ("Phone dumps", _count_files(config.DUMP_DIR)),
        ("Screenshots", _count_files(config.SCREENSHOT_DIR)),
        ("Reports", _count_files(config.REPORT_DIR)),
    ] + [(label, _count_rows(table)) for label, table in _TABLES]
    items = [(label, n) for label, n in counts if n]
    return {"present": bool(items), "items": items}
