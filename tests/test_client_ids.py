"""Client IDs, intake-form timestamps and the "devices scanned for this
client" list (issue #21)."""

import re
import sqlite3
import time
from datetime import datetime

import config
import pytest
import clientwords
import web
import web.view
from phone_scanner import blocklist
from phone_scanner import db as phone_db


@pytest.fixture
def app_db():
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    phone_db.init_db(web.app, None)
    with web.app.app_context():
        yield


def _execute(sql, args=()):
    con = sqlite3.connect(config.SQL_DB_PATH.replace("sqlite:///", ""))
    try:
        rows = con.execute(sql, args).fetchall()
        con.commit()
        return rows
    finally:
        con.close()


def _intake(clientid, created_at="now"):
    _execute(
        "insert into clients_notes (clientid, created_at) values (?, datetime(?, 'localtime'))"
        if created_at == "now" else
        "insert into clients_notes (clientid, created_at) values (?, ?)",
        (clientid, created_at),
    )


def _scan(clientid, serial="HSN_x", model="Pixel 7", owner="me"):
    _execute(
        "insert into scan_res (clientid, serial, device, device_model, device_primary_user) values (?, ?, 'android', ?, ?)",
        (clientid, serial, model, owner),
    )


WORD_ID = re.compile(r"^[a-z]{3,9}(-[a-z]{3,9}){3}$")


def test_a_client_id_is_four_random_words(app_db):
    cid = phone_db.new_client_id()
    assert WORD_ID.match(cid), cid
    words = cid.split("-")
    assert len(set(words)) == 4
    assert all(w in clientwords.WORDS for w in words)


def test_ids_carry_no_date_or_count(app_db):
    # The old IDs (20261010_003) told anyone who saw one the day of the
    # consultation and how many clients came before.
    cid = phone_db.new_client_id()
    assert not re.search(r"\d", cid)


def test_ids_differ_from_one_client_to_the_next(app_db):
    ids = {phone_db.new_client_id() for _ in range(200)}
    assert len(ids) == 200


def test_an_id_already_in_use_is_drawn_again(app_db, monkeypatch):
    _intake("amber-otter-canyon-teapot")
    draws = iter([["amber", "otter", "canyon", "teapot"], ["maple", "otter", "canyon", "teapot"]])
    monkeypatch.setattr(clientwords, "_draw", lambda n: next(draws))
    assert phone_db.new_client_id() == "maple-otter-canyon-teapot"


def test_an_id_used_only_by_a_scan_is_also_taken(app_db, monkeypatch):
    _scan("amber-otter-canyon-teapot")
    draws = iter([["amber", "otter", "canyon", "teapot"], ["maple", "otter", "canyon", "teapot"]])
    monkeypatch.setattr(clientwords, "_draw", lambda n: next(draws))
    assert phone_db.new_client_id() == "maple-otter-canyon-teapot"


def test_the_word_list_is_large_and_clean():
    words = clientwords.WORDS
    assert len(words) >= 2900
    assert len(set(words)) == len(words)
    assert all(re.fullmatch(r"[a-z]{3,9}", w) for w in words)


# Words that must never appear in an ID someone else might see on a screen or
# a piece of paper. Not exhaustive; it guards against careless additions.
NEVER = {"abuse", "spy", "track", "stalk", "watch", "monitor", "camera", "gun", "knife", "rope", "chain",
         "kill", "dead", "blood", "hurt", "fear", "trap", "cage", "lock", "hammer", "arrow", "wolf",
         "drug", "beer", "wine", "date", "kiss", "naked", "police", "court", "jail", "victim", "escape"}


def test_the_word_list_avoids_alarming_words():
    assert NEVER.isdisjoint(clientwords.WORDS)


def test_a_new_client_session_gets_a_word_id(app_db):
    c = web.app.test_client()
    c.get("/")
    with c.session_transaction() as s:
        assert WORD_ID.match(s["clientid"])


def test_deleting_client_data_starts_a_new_client(app_db, monkeypatch):
    monkeypatch.setattr("web.view.evidence.delete_client_data", lambda: None)
    c = web.app.test_client()
    c.get("/")
    with c.session_transaction() as s:
        first = s["clientid"]
    c.post("/evidence/delete-data")
    c.get("/")
    with c.session_transaction() as s:
        assert s["clientid"] != first


def test_evidence_scans_are_saved_under_the_session_client(app_db, monkeypatch):
    # They were all saved under client ID "1".
    import evidence_collection as ec
    import scanflow

    seen = {}

    def fake_run(sc, **kw):
        seen.update(kw)
        raise scanflow.ScanFailed("stop")

    monkeypatch.setattr(scanflow, "run_device_scan", fake_run)
    monkeypatch.setattr(ec, "get_scan_obj", lambda device, nickname: object())
    monkeypatch.setattr(ec, "get_ser_from_scan_obj", lambda sc: "ZY1")
    c = web.app.test_client()
    c.get("/")
    with c.session_transaction() as s:
        cid = s["clientid"]
    c.post("/evidence/scan", data={"device_type": "android", "device_nickname": "phone", "submit": "y"})
    assert seen.get("clientid") == cid


@pytest.fixture
def five_hours_behind_utc(monkeypatch):
    monkeypatch.setenv("TZ", "XXX+5")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_the_intake_form_is_stamped_in_local_time(app_db, five_hours_behind_utc):
    from web.model import Client

    web.sa.session.add(Client(clientid="20261010_001"))
    web.sa.session.commit()
    ((stamp, local_now),) = _execute("select created_at, datetime('now', 'localtime') from clients_notes")
    gap = abs((datetime.fromisoformat(local_now) - datetime.fromisoformat(stamp)).total_seconds())
    assert gap < 120


def test_only_this_clients_devices_are_listed(app_db):
    _scan("20261009_004", serial="HSN_old", model="Old Client Phone")
    _scan("20261010_001", serial="HSN_new", model="Pixel 7")
    devices = phone_db.get_client_devices_from_db("20261010_001")
    assert [d["device_model"] for d in devices] == ["Pixel 7"]


def test_a_client_without_scans_has_no_devices(app_db):
    _scan("20261009_004", serial="HSN_old")
    assert phone_db.get_client_devices_from_db("20261010_001") == []


def test_the_scan_page_does_not_show_another_clients_device(app_db):
    _scan("20261009_004", serial="HSN_old", model="Old Client Phone")
    c = web.app.test_client()
    with c.session_transaction() as s:
        s["clientid"] = "20261010_001"
    page = c.get("/scan?device=android&device_owner=me").get_data(as_text=True)
    assert "Old Client Phone" not in page
    assert "Devices scanned for this client" not in page


def test_flag_colours_are_chosen_by_the_view():
    # Presentation, so not in the scanner's blocklist module.
    assert not hasattr(blocklist, "assign_class")
    flag_class = web.app.jinja_env.filters["flag_class"]
    # The same thresholds blocklist.assign_class used.
    assert flag_class([]) == ""
    assert flag_class(None) == ""
    assert flag_class(["system-app"]) == ""
    assert flag_class(["regex-spy"]) == "alert-info"
    assert flag_class(["dual-use"]) == "alert-warning"
    assert flag_class(["onstore-spyware"]) == "alert-primary"
