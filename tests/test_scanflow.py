"""The scan steps shared by the classic scan page and the evidence workflow
(issue #20): read the device, find its apps, save the scan and its apps."""

import sqlite3
import sys

import pandas as pd
import pytest

import web
import web.view  # noqa: F401
import config
import evidence_collection as ec
import scanflow
from phone_scanner import db as phone_db

SER = "ZY22SHARED"


class FakeScanner:
    def __init__(self, apps=None):
        self.apps = apps if apps is not None else {
            "com.spy": {"title": "Spy App", "flags": ["spyware"]},
            "com.calc": {"title": "Calculator", "flags": []},
        }

    def devices(self):
        return [SER]

    def device_info(self, serial):
        return "Pixel 7 (Android 14)", {"model": "Pixel 7", "version": "14", "brand": "Google"}

    def find_spyapps(self, serialno, from_dump=False):
        return pd.DataFrame.from_dict(self.apps, orient="index")

    def isrooted(self, serial):
        return False, "No indicators."

    def dump_path(self, serial, kind):
        return "/nonexistent"


@pytest.fixture
def app_db():
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    phone_db.init_db(web.app, None)
    with web.app.app_context():
        yield


def _rows(sql):
    con = sqlite3.connect(config.SQL_DB_PATH.replace("sqlite:///", ""))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _scan(sc, **kw):
    args = dict(device="android", ser=SER, device_owner="me", clientid="20261010_001")
    args.update(kw)
    return scanflow.run_device_scan(sc, **args)


def test_a_scan_is_saved_with_its_apps(app_db):
    result = _scan(FakeScanner())
    assert result.scanid > 0
    assert result.device_name == "Pixel 7 (Android 14)"
    assert set(result.apps) == {"com.spy", "com.calc"}
    assert _rows("select clientid, serial, device_model from scan_res") == [
        ("20261010_001", config.hmac_serial(SER), "Pixel 7")]
    assert sorted(r[0] for r in _rows("select appid from app_info")) == ["com.calc", "com.spy"]


def test_no_apps_means_the_scan_failed_and_nothing_is_saved(app_db):
    with pytest.raises(scanflow.ScanFailed, match="scanning failed"):
        _scan(FakeScanner(apps={}))
    assert _rows("select * from scan_res") == []


def test_reading_a_dump_needs_an_earlier_scan(app_db):
    with pytest.raises(scanflow.ScanFailed, match="does not have a scan yet"):
        _scan(FakeScanner(), from_dump=True)
    assert _rows("select * from scan_res") == []


def test_reading_a_dump_reuses_the_earlier_scan(app_db):
    first = _scan(FakeScanner())
    again = _scan(FakeScanner(), from_dump=True)
    assert again.scanid == first.scanid
    assert again.device_name == "Pixel 7 (me)"
    assert len(_rows("select * from scan_res")) == 1


def test_the_raw_serial_is_only_in_the_returned_record_when_asked(app_db):
    assert "serial_or_udid" not in _scan(FakeScanner()).scan
    assert _scan(FakeScanner(), include_raw_serial=True).scan["serial_or_udid"] == SER


@pytest.fixture
def shared_flow_fails(monkeypatch):
    def fail(*a, **k):
        raise scanflow.ScanFailed("SHARED-FLOW-MARKER")

    monkeypatch.setattr(scanflow, "run_device_scan", fail)


def test_the_classic_scan_page_uses_the_shared_steps(app_db, shared_flow_fails, monkeypatch):
    monkeypatch.setattr(sys.modules["web.view.scan"], "get_device", lambda device: FakeScanner())
    c = web.app.test_client()
    with c.session_transaction() as s:
        s["clientid"] = "20261010_001"
    page = c.get("/scan?device=android&device_owner=me").get_data(as_text=True)
    assert "SHARED-FLOW-MARKER" in page


def test_the_evidence_scan_uses_the_shared_steps(app_db, shared_flow_fails, monkeypatch):
    monkeypatch.setattr(ec, "get_scan_obj", lambda device, nickname: FakeScanner())
    monkeypatch.setattr(ec, "get_ser_from_scan_obj", lambda sc: SER)
    with pytest.raises(scanflow.ScanFailed, match="SHARED-FLOW-MARKER"):
        ec.get_scan_data("android", "phone", "amber-otter-canyon-teapot")


class Devices:
    def __init__(self, serials):
        self.serials = serials

    def devices(self):
        return self.serials


def test_the_first_connected_device_is_used():
    assert scanflow.find_serial(Devices(["ZY1", "ZY2"])) == "ZY1"


def test_no_connected_device_is_a_failed_scan():
    with pytest.raises(scanflow.ScanFailed, match="wasn't detected"):
        scanflow.find_serial(Devices([]))


def test_a_given_serial_is_used_but_still_checked():
    assert scanflow.find_serial(Devices([]), "ZY9") == "ZY9"
    with pytest.raises(scanflow.ScanFailed, match="cannot use"):
        scanflow.find_serial(Devices([]), "ZY9; rm -rf /")


def test_the_evidence_scan_refuses_a_serial_it_cannot_use(monkeypatch):
    # The evidence path used to pass whatever the device reported on to the scanner.
    monkeypatch.setattr(ec, "get_device", lambda device: Devices(["$(id)"]))
    with pytest.raises(scanflow.ScanFailed, match="cannot use"):
        ec.get_serial("android", "phone")


def test_no_view_passes_the_unused_owner_choices():
    import inspect

    for name in ("scan", "privacy", "instructions", "details"):
        assert "DEVICE_PRIMARY_USER" not in inspect.getsource(sys.modules[f"web.view.{name}"])
