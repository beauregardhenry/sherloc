"""The classic scan page (/scan), with the phone replaced by a fake scanner."""

import sqlite3
import sys

import pandas as pd
import pytest

import web
import web.view  # noqa: F401
import config
from phone_scanner import db as phone_db

SER = "ZY22CLASSIC"


class FakeScanner:
    def __init__(self, serials=(SER,), apps=None):
        self.serials = list(serials)
        self.apps = apps if apps is not None else {
            "com.spy": {"title": "Spy App", "flags": ["spyware"]},
            "com.calc": {"title": "Calculator", "flags": []},
        }

    def devices(self):
        return self.serials

    def device_info(self, serial):
        return "Pixel 7 (Android 14)", {"model": "Pixel 7", "version": "14", "brand": "Google"}

    def find_spyapps(self, serialno, from_dump=False):
        return pd.DataFrame.from_dict(self.apps, orient="index")

    def isrooted(self, serial):
        return False, "No indicators."

    def dump_path(self, serial, kind):
        return "/nonexistent"


@pytest.fixture
def client(monkeypatch):
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    phone_db.init_db(web.app, None)
    scanner = FakeScanner()
    # web.view re-exports the view function `scan`, which hides the module of that name.
    scan_module = sys.modules["web.view.scan"]
    monkeypatch.setattr(scan_module, "get_device", lambda device: scanner if device in ("android", "ios") else None)
    c = web.app.test_client()
    with c.session_transaction() as s:
        s["clientid"] = "20261010_001"
    c.scanner = scanner
    return c


def _rows(sql):
    con = sqlite3.connect(config.SQL_DB_PATH.replace("sqlite:///", ""))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _scan(client, **params):
    data = {"device": "android", "device_owner": "kitchen phone"}
    data.update(params)
    return client.post("/scan", data=data)


def test_without_a_client_session_it_goes_home():
    web.app.config.update(TESTING=True)
    r = web.app.test_client().get("/scan")
    assert r.status_code in (302, 303)


def test_a_device_type_is_required(client):
    r = _scan(client, device="")
    assert r.status_code == 201
    assert "Please choose one device" in r.get_data(as_text=True)


def test_a_nickname_is_required(client):
    r = _scan(client, device_owner="")
    assert r.status_code == 201
    assert "nickname" in r.get_data(as_text=True)


def test_no_connected_device_points_to_the_setup_instructions(client):
    client.scanner.serials = []
    r = _scan(client)
    assert r.status_code == 201
    assert "detected" in r.get_data(as_text=True)


def test_a_serial_reported_by_the_device_is_validated(client):
    client.scanner.serials = ["x;rm -rf /"]
    r = _scan(client)
    assert r.status_code == 201
    assert "cannot use" in r.get_data(as_text=True)


def test_a_scan_is_recorded_with_its_apps(client):
    r = _scan(client)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Spy App" in body
    scans = _rows("select serial, device_model, device_primary_user, rooted_reasons from scan_res")
    assert scans == [(config.hmac_serial(SER), "Pixel 7", "kitchen phone", "No indicators.")]
    assert {r[0] for r in _rows("select appid from app_info")} == {"com.spy", "com.calc"}


def test_the_raw_serial_is_not_stored(client):
    _scan(client)
    dump = "\n".join(str(r) for r in _rows("select * from scan_res"))
    assert SER not in dump


def test_a_scan_that_finds_no_apps_says_so(client):
    client.scanner.apps = {}
    r = _scan(client)
    assert r.status_code == 201
    assert "scanning failed" in r.get_data(as_text=True)
    assert _rows("select count(*) from scan_res") == [(0,)]


def test_reading_from_a_dump_needs_an_earlier_scan(client):
    r = _scan(client, from_dump="1")
    assert r.status_code == 201
    assert "does not have a scan yet" in r.get_data(as_text=True)


def test_reading_from_a_dump_uses_the_earlier_scan(client):
    # The database stores the pseudonymized serial. The dump path looked the
    # device up by the raw serial, so it never found the earlier scan.
    _scan(client)
    r = _scan(client, from_dump="1")
    assert r.status_code == 200
    assert "Pixel 7 (kitchen phone)" in r.get_data(as_text=True)
    assert _rows("select count(*) from scan_res") == [(1,)]
    scanid = _rows("select id from scan_res")[0][0]
    assert {row[0] for row in _rows("select scanid from app_info")} == {scanid}
