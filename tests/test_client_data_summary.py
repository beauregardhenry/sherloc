"""The page shows when client data is stored on this computer."""

import sqlite3
from pathlib import Path

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import clientdata
import config
from web import app

SCHEMA = Path(config.THIS_DIR) / "web" / "schema.sql"


@pytest.fixture
def empty(tmp_path, monkeypatch):
    for name in ("DUMP_DIR", "SCREENSHOT_DIR", "REPORT_DIR"):
        d = tmp_path / name
        d.mkdir()
        monkeypatch.setattr(config, name, d)
    monkeypatch.setattr(config, "REPORT_PATH", tmp_path / "REPORT_DIR")
    monkeypatch.setattr(config, "CONSULT_DATA_DIR", tmp_path / "consult")
    (tmp_path / "consult").mkdir()
    db = tmp_path / "fieldstudy.db"
    con = sqlite3.connect(db)
    con.executescript(SCHEMA.read_text())
    con.commit()
    con.close()
    monkeypatch.setattr(config, "SQL_DB_PATH", f"sqlite:///{db}")
    return tmp_path


def test_nothing_stored_means_nothing_to_show(empty):
    s = clientdata.summary()
    assert s["present"] is False
    assert s["items"] == []


def test_lock_files_are_not_client_data(empty):
    (empty / "consult" / "notes.json.lock").write_text("")
    assert clientdata.summary()["present"] is False


def test_saved_consultation_files_are_counted(empty):
    (empty / "consult" / "notes.json").write_text("{}")
    s = clientdata.summary()
    assert s["present"] is True
    assert ("Saved consultation answers", 1) in s["items"]


def test_dumps_screenshots_and_reports_are_counted(empty):
    (empty / "DUMP_DIR" / "abc_android.txt").write_text("x")
    sub = empty / "SCREENSHOT_DIR" / "ser" / "root"
    sub.mkdir(parents=True)
    (sub / "a.png").write_bytes(b"x")
    (sub / "b.png").write_bytes(b"x")
    (empty / "REPORT_DIR" / "r.pdf").write_bytes(b"x")
    items = dict(clientdata.summary()["items"])
    assert items["Phone dumps"] == 1
    assert items["Screenshots"] == 2
    assert items["Reports"] == 1


def test_database_rows_are_counted(empty):
    con = sqlite3.connect(empty / "fieldstudy.db")
    con.execute("insert into clients_notes (clientid, general_notes) values ('c', 'n')")
    con.execute("insert into scan_res (clientid, serial) values ('c', 's')")
    con.commit()
    con.close()
    items = dict(clientdata.summary()["items"])
    assert items["Client notes in the database"] == 1
    assert items["Device scans in the database"] == 1


def test_a_missing_database_is_not_an_error(empty):
    (empty / "fieldstudy.db").unlink()
    assert clientdata.summary()["present"] is False


def test_the_page_says_client_data_is_stored(empty):
    (empty / "consult" / "notes.json").write_text("{}")
    app.config.update(TESTING=True)
    html = app.test_client().get("/evidence/home").get_data(as_text=True)
    assert "Client data is stored on this computer" in html


def test_the_page_says_nothing_when_there_is_no_data(empty):
    app.config.update(TESTING=True)
    html = app.test_client().get("/evidence/home").get_data(as_text=True)
    assert "Client data is stored on this computer" not in html
