"""IosScan and IosDump against fake tools and a small synthetic dump."""

import json

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
from phone_scanner import IosScan, parse_dump

UDID = "00008030001a2c3e0a01802e"

USBMUX = json.dumps(
    [
        {"Identifier": UDID, "ConnectionType": "USB", "DeviceName": "x"},
        {"Identifier": "bad;id", "ConnectionType": "USB"},
    ],
    indent=4,
)

APPS = {
    "com.apple.mobilecal": {
        "ApplicationType": "System",
        "CFBundleIdentifier": "com.apple.mobilecal",
        "CFBundleName": "Calendar",
        "CFBundleExecutable": "MobileCal",
        "CFBundleVersion": "1.0",
        "Entitlements": {
            "com.apple.private.tcc.allow": ["kTCCServiceCalendar", ["kTCCServiceReminders"]],
        },
    },
    "com.example.tracker": {
        "ApplicationType": "User",
        "CFBundleIdentifier": "com.example.tracker",
        "CFBundleName": "Tracker",
        "CFBundleExecutable": "Tracker",
        "CFBundleVersion": "2.3",
        "Entitlements": {},
        "NSCalendarsUsageDescription": "Needed to see your calendar",
    },
}

INFO = {
    "DeviceClass": "iPhone",
    "ProductType": "iPhone99,1",
    "ModelNumber": "MX1",
    "RegionInfo": "LL/A",
    "ProductVersion": "17.4",
}


@pytest.fixture
def dump_files(tmp_path):
    apps = tmp_path / "ios_apps.json"
    info = tmp_path / "ios_info.xml"
    apps.write_text(json.dumps(APPS))
    info.write_text(json.dumps(INFO))
    return apps, info


@pytest.fixture
def dump(dump_files):
    apps, info = dump_files
    return parse_dump.IosDump(str(apps), finfo=str(info))


def test_devices_lists_valid_identifiers(fake_bin):
    fake_bin("pymobiledevice3", [{"match": "usbmux list", "stdout": USBMUX}])
    assert IosScan().devices() == [UDID]


def test_devices_is_empty_when_nothing_is_attached(fake_bin):
    fake_bin("pymobiledevice3", [{"match": "usbmux list", "stdout": "[]"}])
    assert IosScan().devices() == []


def test_uninstall_targets_the_scanned_device(fake_bin):
    tool = fake_bin("ideviceinstaller", [{"match": "--uninstall", "stdout": "Complete\n"}])
    assert IosScan().uninstall(UDID, "com.example.tracker") is True
    assert ["--udid", UDID, "--uninstall", "com.example.tracker"] in tool.calls


@pytest.mark.parametrize("serial,appid", [("x; id", "com.a"), (UDID, "$(id)"), (UDID, "a b")])
def test_uninstall_refuses_unsafe_input_before_running_anything(fake_bin, serial, appid):
    tool = fake_bin("ideviceinstaller")
    with pytest.raises(ValueError):
        IosScan().uninstall(serial, appid)
    assert tool.calls == []


def test_uninstall_reports_failure_when_the_tool_fails(fake_bin):
    fake_bin("ideviceinstaller", [{"match": "--uninstall", "stderr": "ERROR: Uninstall failed", "rc": 1}])
    assert IosScan().uninstall(UDID, "com.example.tracker") is False


def test_dump_runs_the_script_with_the_pseudonymized_serial(fake_bin, tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    from tests.fakebin import FakeTool

    script = FakeTool(scripts, "ios_dump.sh", [{"match": "", "stdout": "dumped\n"}])
    monkeypatch.setattr(config, "SCRIPT_DIR", scripts)
    assert IosScan()._dump_phone(UDID) is True
    (call,) = script.calls
    assert call[0] == config.hmac_serial(UDID)
    assert call[1:] == [
        config.IOS_DUMPFILES[k] for k in ("Apps", "Info", "Jailbroken-FS", "Jailbroken-SSH")
    ]


def test_dump_fails_when_the_script_prints_nothing(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    from tests.fakebin import FakeTool

    FakeTool(scripts, "ios_dump.sh", [{"match": "", "stdout": ""}])
    monkeypatch.setattr(config, "SCRIPT_DIR", scripts)
    assert IosScan()._dump_phone(UDID) is False


def test_dump_lists_all_apps(dump):
    assert sorted(dump.installed_apps()) == ["com.apple.mobilecal", "com.example.tracker"]
    assert len(dump) == 2


def test_system_apps_are_the_ones_apple_ships(dump):
    assert list(dump.system_apps()) == ["com.apple.mobilecal"]


def test_device_info_names_the_model_and_version(dump):
    text, info = dump.device_info()
    assert text.endswith("(running iOS 17.4)")
    assert info["version"] == "17.4"


def test_app_info_has_title_version_and_permissions(dump):
    info = dump.info("com.example.tracker")
    assert info["title"] == "Tracker"
    assert info["App Version"] == "2.3"
    assert ("Calendars", "Needed to see your calendar") in info["permissions"]


def test_system_app_permissions_come_from_entitlements_including_nested(dump):
    names = {p for p, _ in dump.info("com.apple.mobilecal")["permissions"]}
    assert {"Calendars", "Reminders"} <= names


def test_a_missing_dump_file_gives_an_empty_listing(tmp_path):
    d = parse_dump.IosDump(str(tmp_path / "nope.json"))
    assert d.installed_apps() == []


def test_a_missing_info_file_still_loads(dump_files, tmp_path):
    apps, _ = dump_files
    d = parse_dump.IosDump(str(apps), finfo=str(tmp_path / "missing.xml"))
    assert d.device_class == ""


def test_dump_fails_when_the_script_fails(tmp_path, monkeypatch):
    # catch_err used to return the error message, which counted as output,
    # so a failed dump was reported as a success.
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    from tests.fakebin import FakeTool

    FakeTool(scripts, "ios_dump.sh", [{"match": "", "stderr": "ERROR: No device found\n", "rc": 1}])
    monkeypatch.setattr(config, "SCRIPT_DIR", scripts)
    assert IosScan()._dump_phone(UDID) is False
