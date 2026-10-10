"""Client IDs, intake-form timestamps and the "devices scanned for this
client" list (issue #21)."""

import sqlite3
import time
from datetime import datetime

import config
import pytest
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


def _today():
    return datetime.now().strftime("%Y%m%d")  # noqa: DTZ005 - client IDs use local dates


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


def test_the_first_client_of_the_day_is_001(app_db):
    assert phone_db.new_client_id() == f"{_today()}_001"


def test_the_next_client_follows_the_highest_number_today(app_db):
    _intake(f"{_today()}_002")
    _intake(f"{_today()}_010")
    assert phone_db.new_client_id() == f"{_today()}_011"


def test_an_id_in_another_format_does_not_break_it(app_db):
    # It used to split on "_" and fail on anything else.
    _intake("walk-in")
    _intake(f"{_today()}_003")
    assert phone_db.new_client_id() == f"{_today()}_004"


def test_yesterdays_clients_do_not_count_whatever_the_timestamp(app_db):
    # Rows saved in UTC could look like today in local time, and the next ID
    # then carried yesterday's date.
    _intake("20000101_007", created_at="9999-01-01 00:00:00")
    assert phone_db.new_client_id() == f"{_today()}_001"


def test_todays_client_is_counted_even_with_an_old_timestamp(app_db):
    # The reverse: a UTC timestamp before local midnight hid today's client,
    # and the next client got the same ID.
    _intake(f"{_today()}_001", created_at="2000-01-01 00:00:00")
    assert phone_db.new_client_id() == f"{_today()}_002"


def test_a_client_with_scans_but_no_intake_form_is_counted(app_db):
    _scan(f"{_today()}_001")
    assert phone_db.new_client_id() == f"{_today()}_002"


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
