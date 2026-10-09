"""Client data must not be printed to the terminal.

Terminal output outlives "Delete client data": it stays in scrollback, in a
service journal, or in a file when the app is started with `> log`. Notes,
client names, device serials and installed-app lists are client data.
Output is only allowed with DEBUG=1.
"""

import json

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
import evidence_collection as ec
from phone_scanner import AndroidScan, IosScan, android_permissions as perms, parse_dump
from web import app

NOTE = "MARKER-NOTE-90417"
NAME = "MARKER-CLIENT-90417"
SERIAL = "R58M9041ABCD"
UDID = "00008030001a2c3e0a019041"
APP = "com.marker.app90417"


@pytest.fixture(autouse=True)
def _quiet(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DEBUG", False)
    monkeypatch.setattr(ec, "TMP_CONSULT_DATA_DIR", str(tmp_path))


def _output(capfd):
    out, err = capfd.readouterr()
    return out + err


def _assert_clean(capfd, *secrets):
    text = _output(capfd)
    for s in secrets:
        assert s not in text, f"{s!r} was printed to the terminal"


def test_saving_notes_prints_nothing_from_the_form(capfd):
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    r = app.test_client().post(
        "/evidence/home",
        data={"client_name": NAME, "consultant_notes": NOTE, "client_notes": NOTE, "submit": "y"},
    )
    assert r.status_code in (200, 302)
    _assert_clean(capfd, NOTE, NAME)


def test_showing_the_home_page_prints_no_saved_notes(capfd):
    ec.save_data_as_json(
        ec.ConsultNotesData(consultant_notes=NOTE, client_notes=NOTE, client_name=NAME),
        ec.ConsultDataTypes.NOTES.value,
    )
    app.config.update(TESTING=True)
    assert app.test_client().get("/evidence/home").status_code == 200
    _assert_clean(capfd, NOTE, NAME)


def test_android_scanning_prints_no_serial_or_apps(fake_adb, capfd):
    fake_adb.respond([
        {"match": "devices", "stdout": f"List of devices attached\n{SERIAL}\tdevice\n"},
        {"match": "list packages", "stdout": f"package:{APP}\n"},
        {"match": "ro.product.brand", "stdout": "samsung\n"},
        {"match": "command -v su", "stdout": "0\n"},
    ])
    scan = AndroidScan()
    assert scan.devices() == [SERIAL]
    assert scan._get_apps_from_device(SERIAL, "-u") == [APP]
    scan.device_info(SERIAL)
    scan.isrooted(SERIAL)
    scan.uninstall(SERIAL, APP)
    _assert_clean(capfd, SERIAL, APP)


def test_ios_scanning_prints_no_udid(fake_bin, capfd):
    fake_bin("pymobiledevice3", [{"match": "usbmux list", "stdout": json.dumps([{"Identifier": UDID}], indent=4)}])
    fake_bin("ideviceinstaller")
    scan = IosScan()
    assert scan.devices() == [UDID]
    scan.uninstall(UDID, APP)
    _assert_clean(capfd, UDID, APP)


def test_reading_a_dump_prints_no_app_ids(tmp_path, capfd):
    (tmp_path / "x_android.txt").write_text(
        f"DUMP OF SERVICE package\nPackages:\n  Package [{APP}] (Marker):\n    userId=1\n"
    )
    dump = parse_dump.AndroidDump(str(tmp_path / "x_android.json"))
    dump.apps()
    dump.info(APP)
    _assert_clean(capfd, APP)


def test_reading_an_ios_dump_prints_no_app_ids(tmp_path, capfd):
    apps = {APP: {"ApplicationType": "User", "CFBundleIdentifier": APP, "CFBundleName": "M",
                  "CFBundleExecutable": "M", "CFBundleVersion": "1", "Entitlements": {}}}
    (tmp_path / "apps.json").write_text(json.dumps(apps))
    d = parse_dump.IosDump(str(tmp_path / "apps.json"))
    d.installed_apps()
    d.info(APP)
    _assert_clean(capfd, APP)


def test_permission_lookup_prints_no_raw_device_output(fake_adb, capfd):
    fake_adb.respond([{"match": "appops get", "stdout": "CAMERA: allow; time=+1m1s1ms ago; duration=+1s1ms\n"}])
    perms.recent_permissions_used(APP)
    _assert_clean(capfd, APP, "CAMERA")


def test_debug_mode_still_prints(monkeypatch, fake_adb, capfd):
    monkeypatch.setattr(config, "DEBUG", True)
    fake_adb.respond([{"match": "devices", "stdout": f"List of devices attached\n{SERIAL}\tdevice\n"}])
    AndroidScan().devices()
    assert SERIAL in _output(capfd)
