"""AndroidScan against a fake `adb`.

The fake records every call, so these tests pin both what the scanner parses
and which commands it sends to the device.
"""

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
from phone_scanner import AndroidScan

SERIAL = "R58M123ABCD"

DEVICES = (
    "List of devices attached\n"
    f"{SERIAL}\tdevice\n"
    "0123456789ABCDEF\toffline\n"
    "emulator-5554\tdevice\n"
    "\n"
)


@pytest.fixture
def adb(fake_bin, monkeypatch):
    tool = fake_bin("adb")
    monkeypatch.setattr(config, "ADB_PATH", str(tool.path))
    return tool


@pytest.fixture
def scan(adb):
    return AndroidScan()


def test_devices_lists_only_connected_devices(scan, adb):
    adb.respond([{"match": "devices", "stdout": DEVICES}])
    assert scan.devices() == [SERIAL, "emulator-5554"]


def test_devices_ignores_a_serial_that_is_unsafe_to_use(scan, adb):
    adb.respond([{"match": "devices", "stdout": "List of devices attached\nbad;id\tdevice\n"}])
    assert scan.devices() == []


def test_devices_is_empty_when_adb_prints_nothing(scan, adb):
    adb.respond([{"match": "devices", "stdout": ""}])
    assert scan.devices() == []


def test_installed_apps_are_listed_without_prefix_and_sorted(scan, adb):
    adb.respond([
        {"match": "list packages -u", "stdout": "package:com.zeta\npackage:com.alpha\npackage:com.mid\n"}
    ])
    assert scan._get_apps_from_device(SERIAL, "-u") == ["com.alpha", "com.mid", "com.zeta"]
    assert ["-s", SERIAL, "shell", "pm", "list", "packages", "-u"] in adb.calls


def test_system_apps_use_the_system_flag(scan, adb):
    adb.respond([{"match": "list packages -s", "stdout": "package:com.android.settings\n"}])
    assert scan.get_system_apps(SERIAL) == ["com.android.settings"]


def test_a_failed_listing_restarts_the_adb_server(scan, adb):
    adb.respond([{"match": "list packages", "stdout": "", "rc": 1, "stderr": "error: closed"}])
    assert scan._get_apps_from_device(SERIAL, "-u") == []
    calls = [c[0] for c in adb.calls if c]
    assert "kill-server" in calls and "start-server" in calls


def test_offstore_apps_are_those_not_from_an_approved_installer(scan, adb, monkeypatch):
    monkeypatch.setattr(config, "APPROVED_INSTALLERS", {"com.android.vending"})
    adb.respond([
        {"match": "packages -i -u -s", "stdout": "package:com.android.settings  installer=null\n"},
        {
            "match": "packages -i -u -3",
            "stdout": (
                "package:com.good  installer=com.android.vending\n"
                "package:com.sideloaded  installer=com.example.store\n"
            ),
        },
    ])
    assert scan.get_offstore_apps(SERIAL) == ["com.sideloaded"]


@pytest.mark.xfail(
    strict=True, reason="brand and model keep the newline that getprop prints"
)
def test_device_info_reads_brand_model_and_version(scan, adb):
    adb.respond([
        {"match": "ro.product.brand", "stdout": "samsung\n"},
        {"match": "ro.product.model", "stdout": "SM-G991U\n"},
        {"match": "ro.build.version.release", "stdout": "13\n"},
    ])
    text, info = scan.device_info(SERIAL)
    assert text == "Samsung SM-G991U (running Android 13)"
    assert info["brand"] == "Samsung"


def test_device_info_rejects_an_unsafe_serial(scan):
    with pytest.raises(ValueError):
        scan.device_info("x; touch /tmp/pwned")


def test_phone_is_rooted_when_a_check_matches(scan, adb):
    adb.respond([{"match": "command -v su", "stdout": "0\n"}])
    rooted, why = scan.isrooted(SERIAL)
    assert rooted is True
    assert "su binary" in why
    assert ["-s", SERIAL, "shell", "command -v su"] in adb.calls


def test_phone_is_not_rooted_when_no_check_matches(scan, adb):
    rooted, _ = scan.isrooted(SERIAL)
    assert rooted is False


def test_uninstall_targets_the_scanned_device(scan, adb):
    adb.respond([{"match": "uninstall", "stdout": "Success\n"}])
    assert scan.uninstall(SERIAL, "com.spy.app") is True
    assert ["-s", SERIAL, "uninstall", "com.spy.app"] in adb.calls


@pytest.mark.parametrize("serial,appid", [("x; id", "com.a"), (SERIAL, "a b; id"), (SERIAL, "$(id)")])
def test_uninstall_refuses_unsafe_input_before_running_anything(scan, adb, serial, appid):
    with pytest.raises(ValueError):
        scan.uninstall(serial, appid)
    assert adb.calls == []


@pytest.mark.xfail(
    strict=True,
    reason="uninstall() reports success whatever adb returned: catch_err never returns -1",
)
def test_uninstall_reports_failure_when_adb_fails(scan, adb):
    adb.respond([{"match": "uninstall", "stderr": "Failure [DELETE_FAILED_DEVICE_POLICY_MANAGER]", "rc": 1}])
    assert scan.uninstall(SERIAL, "com.spy.app") is False
