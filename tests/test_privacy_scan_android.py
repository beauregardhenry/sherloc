"""The Android privacy-check helpers against a fake `adb`."""

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
from phone_scanner import privacy_scan_android as psa

SERIAL = "R58M123ABCD"


@pytest.fixture
def adb(fake_bin, monkeypatch):
    tool = fake_bin("adb")
    monkeypatch.setattr(config, "ADB_PATH", str(tool.path))
    monkeypatch.setattr(psa, "adb", str(tool.path), raising=False)
    return tool


def test_screen_resolution_is_read_from_dumpsys(adb):
    adb.respond([
        {"match": "dumpsys window", "stdout": "  mUnrestrictedScreen=(0,0) 1080x2400\n  other line\n"}
    ])
    assert psa.get_screen_res(SERIAL) == (1080, 2400)
    assert ["-s", SERIAL, "shell", "dumpsys", "window"] in adb.calls


def test_screen_resolution_is_unknown_when_dumpsys_has_no_match(adb):
    adb.respond([{"match": "dumpsys window", "stdout": "nothing useful\n"}])
    assert psa.get_screen_res(SERIAL) == (-1, -1)


def test_open_activity_succeeds_on_clean_output(adb):
    adb.respond([{"match": "am start", "stdout": "Starting: Intent { cmp=x/.Y }\n"}])
    assert psa.open_activity(SERIAL, "com.android.settings/.Settings") is True
    assert ["-s", SERIAL, "shell", "am", "start", "com.android.settings/.Settings"] in adb.calls


def test_open_activity_keeps_the_escape_the_device_shell_needs(adb):
    # The device shell turns \$ into $, which names the inner class.
    act = r"com.android.settings/.Settings\$PrivacySettingsActivity"
    psa.open_activity(SERIAL, act)
    assert ["-s", SERIAL, "shell", "am", "start", act] in adb.calls


def test_open_activity_fails_when_adb_says_error(adb):
    adb.respond([{"match": "am start", "stdout": "Error: Activity class does not exist.\n"}])
    assert psa.open_activity(SERIAL, "a/.B") is False


def test_open_activity_fails_when_adb_writes_to_stderr(adb):
    adb.respond([{"match": "am start", "stderr": "error: device offline\n", "rc": 1}])
    assert psa.open_activity(SERIAL, "a/.B") is False


def test_open_activity_rejects_an_unsafe_name(adb):
    with pytest.raises(ValueError):
        psa.open_activity(SERIAL, "a/.B; reboot")
    assert adb.calls == []


def test_tap_converts_percent_to_pixels(adb):
    adb.respond([{"match": "dumpsys window", "stdout": "mUnrestrictedScreen=(0,0) 1000x2000\n"}])
    psa.tap(SERIAL, 50, 25)
    assert ["-s", SERIAL, "shell", "input", "tap", "500", "500"] in adb.calls


def test_keycode_sends_the_key_event(adb):
    psa.keycode(SERIAL, "home")
    assert ["-s", SERIAL, "shell", "input", "keyevent", "3"] in adb.calls


@pytest.mark.parametrize("dump,expected", [("  mInteractive=true\n", True), ("  mInteractive=false\n", False), ("", False)])
def test_screen_state_is_read_from_the_input_method_dump(adb, dump, expected):
    adb.respond([{"match": "dumpsys input_method", "stdout": dump}])
    assert psa.is_screen_on(SERIAL) is expected


def test_no_serial_means_the_default_device(adb):
    adb.respond([{"match": "dumpsys window", "stdout": "mUnrestrictedScreen=(0,0) 10x20\n"}])
    assert psa.get_screen_res(None) == (10, 20)
    assert ["shell", "dumpsys", "window"] in adb.calls


def test_an_unsafe_serial_is_refused_before_any_command(adb):
    with pytest.raises(ValueError):
        psa.get_screen_res("x; reboot")
    assert adb.calls == []


def test_screenshot_is_written_from_exec_out(adb, tmp_path):
    adb.respond([{"match": "exec-out screencap -p", "stdout": "PNGDATA"}])
    out = tmp_path / "shot.png"
    with web.app.test_request_context():
        html = psa.take_screenshot(SERIAL, fname=str(out))
    assert out.read_bytes() == b"PNGDATA"
    assert "<img" in html
    assert ["-s", SERIAL, "exec-out", "screencap", "-p"] in adb.calls


def test_a_failed_screenshot_returns_a_visible_message(adb, tmp_path):
    adb.respond([{"match": "screencap", "rc": 1}])
    with web.app.test_request_context():
        html = psa.take_screenshot(SERIAL, fname=str(tmp_path / "x.png"))
    assert "screenshotfail" in html
