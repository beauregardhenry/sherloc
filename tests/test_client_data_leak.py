"""After "Delete client data", nothing of the consultation is left on disk.

The test fills every place the app writes client data, using the app's own
writers, then deletes and searches the whole tree for the marker text. It
looks at file contents, file names, and the database's journal and WAL files.
"""

import sqlite3
from pathlib import Path

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
import evidence_collection as ec
from phone_scanner import db as phone_db
from phone_scanner import parse_dump, privacy_scan_android as psa
from web import app

SCHEMA = Path(config.THIS_DIR) / "web" / "schema.sql"
MARK = "LEAKMARK-5520"
SERIAL = "R58M5520ABCD"


@pytest.fixture
def tree(tmp_path, monkeypatch, fake_adb):
    dirs = {n: tmp_path / n for n in ("dumps", "shots", "reports", "consult", "data")}
    for d in dirs.values():
        d.mkdir()
    for name, key in (("DUMP_DIR", "dumps"), ("SCREENSHOT_DIR", "shots"), ("REPORT_DIR", "reports")):
        monkeypatch.setattr(config, name, dirs[key])
        monkeypatch.setattr(ec, name, dirs[key])
    monkeypatch.setattr(config, "REPORT_PATH", dirs["reports"])
    monkeypatch.setattr(config, "CONSULT_DATA_DIR", dirs["consult"])
    monkeypatch.setattr(ec, "TMP_CONSULT_DATA_DIR", str(dirs["consult"]))
    db = dirs["data"] / "fieldstudy.db"
    monkeypatch.setattr(config, "DB_DIR", dirs["data"])
    monkeypatch.setattr(config, "SQL_DB_PATH", f"sqlite:///{db}")
    monkeypatch.setattr(phone_db, "DATABASE", str(db))
    return tmp_path, dirs, db


def _fill(tmp_path, dirs, db, fake_adb):
    # database, in WAL mode so a -wal file exists
    con = sqlite3.connect(db)
    con.executescript(SCHEMA.read_text())
    con.execute("pragma journal_mode=wal")
    con.execute("insert into clients_notes (clientid, general_notes) values ('c', ?)", (MARK,))
    con.execute("insert into scan_res (clientid, serial) values ('c', ?)", (MARK,))
    con.execute("insert into app_info (scanid, appid, remark) values (1, 'a.b', ?)", (MARK,))
    con.commit()
    keep_open = con  # keeps the WAL file in place until the delete runs

    # consultation answers, saved by the app
    ec.save_data_as_json(
        ec.ConsultNotesData(consultant_notes=MARK, client_notes=MARK, client_name=MARK),
        ec.ConsultDataTypes.NOTES.value,
    )
    # phone dump and its parsed cache, written by the dump parser
    (dirs["dumps"] / f"{MARK}_android.txt").write_text(
        f"DUMP OF SERVICE package\nPackages:\n  Package [com.{MARK}] (App):\n    userId=1\n"
    )
    parse_dump.AndroidDump(str(dirs["dumps"] / f"{MARK}_android.json"))
    ios = dirs["dumps"] / f"{MARK}_ios"
    ios.mkdir()
    (ios / "ios_info.xml").write_text(MARK)
    # a screenshot saved under the device's folder
    fake_adb.respond([{"match": "screencap", "stdout": MARK}])
    fname = config.create_screenshot_fname("root", MARK)
    with app.test_request_context():
        psa.take_screenshot(SERIAL, fname=fname)
    # a CSV report written from the database rows
    with app.app_context():
        phone_db.create_report("c")
    return keep_open




def _leftovers(root):
    found = []
    for p in root.rglob("*"):
        if "fakebin" in p.parts:  # the test's own fake tool, not the app's data
            continue
        if MARK in p.name:
            found.append(f"name: {p}")
        elif p.is_file() and MARK.encode() in p.read_bytes():
            found.append(f"content: {p}")
    return found


def test_nothing_with_the_marker_is_left_after_deleting(tree, fake_adb):
    tmp_path, dirs, db = tree
    con = _fill(tmp_path, dirs, db, fake_adb)
    assert _leftovers(tmp_path), "the test did not store anything"
    con.close()
    ec.delete_client_data()
    assert _leftovers(tmp_path) == []


def test_every_client_data_folder_is_empty_after_deleting(tree, fake_adb):
    tmp_path, dirs, db = tree
    con = _fill(tmp_path, dirs, db, fake_adb)
    con.close()
    ec.delete_client_data()
    for key in ("dumps", "shots", "reports"):
        assert list(dirs[key].iterdir()) == [], key
    leftover = [p.name for p in dirs["consult"].iterdir() if not p.name.endswith(".lock")]
    assert leftover == []
    assert not (dirs["data"] / "fieldstudy.db-wal").exists() or (dirs["data"] / "fieldstudy.db-wal").stat().st_size == 0
