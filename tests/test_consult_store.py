"""Consultation answers (TAQ, scans, accounts, notes) live in the SQLite database.

They used to be four JSON files with lock files next to them, while scan rows
and app remarks were in SQLite. One store means one place to protect, count
and wipe.
"""

import json
import sqlite3
from pathlib import Path

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
import evidence_collection as ec
from phone_scanner import db as phone_db

N = ec.ConsultDataTypes
MARK = "STOREMARK-3381"


@pytest.fixture
def legacy_dir(tmp_path, monkeypatch):
    d = tmp_path / "legacy"
    d.mkdir()
    monkeypatch.setattr(ec, "TMP_CONSULT_DATA_DIR", str(d))
    return d


def _db_file():
    return Path(config.SQL_DB_PATH.replace("sqlite:///", ""))


def _rows():
    con = sqlite3.connect(_db_file())
    try:
        return dict(con.execute("select name, body from consult_documents"))
    finally:
        con.close()


def test_nothing_saved_gives_the_old_defaults(legacy_dir):
    assert ec.load_json_data(N.NOTES.value) == {}
    assert ec.load_json_data(N.TAQ.value) == {}
    assert ec.load_json_data(N.SCANS.value) == []
    assert ec.load_json_data(N.ACCOUNTS.value) == []


def test_saved_data_comes_back(legacy_dir):
    ec.save_data_as_json(
        ec.ConsultNotesData(consultant_notes=MARK, client_notes="b", client_name="c"), N.NOTES.value
    )
    assert ec.load_json_data(N.NOTES.value)["consultant_notes"] == MARK


def test_saving_again_replaces_the_old_answers(legacy_dir):
    for text in ("first", "second"):
        ec.save_data_as_json(
            ec.ConsultNotesData(consultant_notes=text, client_notes="", client_name=""), N.NOTES.value
        )
    assert ec.load_json_data(N.NOTES.value)["consultant_notes"] == "second"
    assert len(_rows()) == 1


def test_each_kind_is_stored_on_its_own(legacy_dir):
    ec.save_data_as_json(
        ec.ConsultNotesData(consultant_notes=MARK, client_notes="", client_name=""), N.NOTES.value
    )
    ec.save_data_as_json([], N.SCANS.value)
    assert set(_rows()) == {"notes", "scans"}
    assert ec.load_json_data(N.SCANS.value) == []


def test_answers_go_to_the_database_not_to_files(legacy_dir):
    ec.save_data_as_json(
        ec.ConsultNotesData(consultant_notes=MARK, client_notes="", client_name=""), N.NOTES.value
    )
    assert list(legacy_dir.iterdir()) == []
    assert MARK in _rows()["notes"]


def test_objects_load_the_same_as_before(legacy_dir):
    ec.save_data_as_json(ec.TAQData(), N.TAQ.value)
    assert isinstance(ec.load_object_from_json(N.TAQ.value), ec.TAQData)
    ec.save_data_as_json([], N.SCANS.value)
    assert ec.load_object_from_json(N.SCANS.value) == []


# --- answers saved by an earlier version, as JSON files ------------------


def _legacy(legacy_dir, name, data):
    (legacy_dir / f"{name}.json").write_text(json.dumps(data))
    (legacy_dir / f"{name}.json.lock").write_text("")


def test_old_json_files_are_still_read(legacy_dir):
    _legacy(legacy_dir, "notes", {"consultant_notes": MARK, "client_notes": "", "client_name": ""})
    assert ec.load_json_data(N.NOTES.value)["consultant_notes"] == MARK


def test_old_json_files_move_into_the_database_and_are_removed(legacy_dir):
    _legacy(legacy_dir, "notes", {"consultant_notes": MARK, "client_notes": "", "client_name": ""})
    ec.load_json_data(N.NOTES.value)
    assert MARK in _rows()["notes"]
    assert not (legacy_dir / "notes.json").exists()
    assert not (legacy_dir / "notes.json.lock").exists()


def test_old_files_of_every_kind_are_moved(legacy_dir):
    _legacy(legacy_dir, "scans", [])
    _legacy(legacy_dir, "accounts", [])
    _legacy(legacy_dir, "taq", {})
    ec.load_json_data(N.SCANS.value)
    assert set(_rows()) == {"scans", "accounts", "taq"}
    assert list(legacy_dir.iterdir()) == []


def test_an_old_file_never_replaces_newer_answers(legacy_dir):
    ec.save_data_as_json(
        ec.ConsultNotesData(consultant_notes="new", client_notes="", client_name=""), N.NOTES.value
    )
    _legacy(legacy_dir, "notes", {"consultant_notes": "old", "client_notes": "", "client_name": ""})
    assert ec.load_json_data(N.NOTES.value)["consultant_notes"] == "new"
    assert not (legacy_dir / "notes.json").exists()


def test_an_unreadable_old_file_is_left_alone(legacy_dir):
    (legacy_dir / "notes.json").write_text("{not json")
    assert ec.load_json_data(N.NOTES.value) == {}
    assert (legacy_dir / "notes.json").exists()


def test_removed_old_files_are_overwritten_first(legacy_dir, monkeypatch):
    _legacy(legacy_dir, "notes", {"consultant_notes": MARK, "client_notes": "", "client_name": ""})
    seen = []
    real_remove = __import__("os").remove

    def spy(path):
        if str(path).endswith("notes.json"):
            seen.append(Path(path).read_bytes())
        real_remove(path)

    monkeypatch.setattr("consultstore.os.remove", spy)
    ec.load_json_data(N.NOTES.value)
    assert seen and MARK.encode() not in seen[0]


# --- deleting -------------------------------------------------------------


def test_deleting_client_data_empties_the_answers_and_the_bytes(legacy_dir, tmp_path, monkeypatch):
    for name in ("DUMP_DIR", "SCREENSHOT_DIR", "REPORT_DIR"):
        d = tmp_path / name
        d.mkdir()
        monkeypatch.setattr(ec, name, d)
    ec.save_data_as_json(
        ec.ConsultNotesData(consultant_notes=MARK, client_notes="", client_name=""), N.NOTES.value
    )
    ec.delete_client_data()
    assert _rows() == {}
    assert MARK.encode() not in _db_file().read_bytes()
    assert ec.load_json_data(N.NOTES.value) == {}


def test_deleting_also_removes_unmigrated_old_files(legacy_dir, tmp_path, monkeypatch):
    for name in ("DUMP_DIR", "SCREENSHOT_DIR", "REPORT_DIR"):
        d = tmp_path / name
        d.mkdir()
        monkeypatch.setattr(ec, name, d)
    _legacy(legacy_dir, "notes", {"consultant_notes": MARK})
    ec.delete_client_data()
    assert list(legacy_dir.iterdir()) == []


# --- the database is set up in one place ----------------------------------


def test_the_schema_has_the_answers_table():
    assert "consult_documents" in (Path(config.THIS_DIR) / "web" / "schema.sql").read_text()


def test_init_db_builds_the_schema_even_if_the_file_already_exists(legacy_dir):
    # Saving answers creates the database file before init_db runs.
    ec.save_data_as_json([], N.SCANS.value)
    assert _db_file().exists()
    phone_db.init_db(web.app, None)
    con = sqlite3.connect(_db_file())
    try:
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    finally:
        con.close()
    assert {"clients_notes", "scan_res", "app_info", "consult_documents"} <= tables
