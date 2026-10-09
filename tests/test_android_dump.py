"""Android dump parsing and permission lookups, from synthetic dumpsys text."""

import datetime

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
from phone_scanner import android_permissions as perms
from phone_scanner import parse_dump

DUMP = """\
DUMP OF SERVICE package
Packages:
  Package [com.spy.app] (abc123):
    userId=10150
    firstInstallTime=2024-01-02 03:04:05
    lastUpdateTime=2024-02-03 04:05:06
    versionName=1.2.3
  Package [com.other] (def456):
    userId=10151
    firstInstallTime=2023-05-06 07:08:09
DUMP OF SETTINGS secure
adb_enabled=1
install_non_market_apps=1
"""


@pytest.fixture
def dumpfile(tmp_path):
    (tmp_path / "abc_android.txt").write_text(DUMP)
    return str(tmp_path / "abc_android.json")


def test_count_lspaces_counts_leading_whitespace():
    assert parse_dump.count_lspaces("    x") == 4
    assert parse_dump.count_lspaces("x") == 0


def test_get_d_at_level_creates_the_path():
    d = {}
    parse_dump.get_d_at_level(d, ["a", "b"])["c"] = 1
    assert d == {"a": {"b": {"c": 1}}}


def test_prune_empty_keys_turns_leaf_keys_into_a_list():
    assert parse_dump.prune_empty_keys({"a": {"x": {}, "y": {}}, "b": {"z": {}}}) == {
        "a": ["x", "y"],
        "b": ["z"],
    }


def test_dump_lists_packages_with_names_sorted(dumpfile):
    d = parse_dump.AndroidDump(dumpfile)
    assert d.apps() == [("com.other", "def456"), ("com.spy.app", "abc123")]


def test_dump_reads_install_times_for_an_app(dumpfile):
    info = parse_dump.AndroidDump(dumpfile).info("com.spy.app")
    assert info["firstInstallTime"] == "2024-01-02 03:04:05"
    assert info["lastUpdateTime"] == "2024-02-03 04:05:06"


def test_dump_caches_the_parsed_result_next_to_the_text(dumpfile, tmp_path):
    parse_dump.AndroidDump(dumpfile)
    assert (tmp_path / "abc_android.json").exists()


def test_an_unknown_app_gives_no_info(dumpfile):
    assert parse_dump.AndroidDump(dumpfile).info("com.nothere") == {}


def test_a_missing_dump_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_dump.AndroidDump(str(tmp_path / "none_android.json"))


def test_settings_sections_are_parsed_as_key_values(dumpfile):
    d = parse_dump.AndroidDump(dumpfile)
    assert d.df["settings_secure"]["install_non_market_apps"] == "1"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("+29d3h41m32s800ms", datetime.timedelta(days=29, hours=3, minutes=41, seconds=32, milliseconds=800)),
        ("+16m12s788ms", datetime.timedelta(minutes=16, seconds=12, milliseconds=788)),
        ("+2h7m13s715ms", datetime.timedelta(hours=2, minutes=7, seconds=13, milliseconds=715)),
    ],
)
def test_parse_time_reads_android_durations(text, expected):
    assert perms._parse_time(text) == expected


APPOPS = (
    "CAMERA: allow; time=+38d23h30m11s6ms ago; duration=+420ms\n"
    "RECORD_AUDIO: allow; time=+16m12s788ms ago; duration=+10s237ms\n"
    "READ_EXTERNAL_STORAGE: allow; time=+2h7m13s715ms ago\n"
)


def test_recent_permissions_used_reads_appops_output(fake_bin):
    adb = fake_bin("adb", [{"match": "appops get com.spy.app", "stdout": APPOPS}])
    df = perms.recent_permissions_used("com.spy.app")
    assert set(df["op"]) == {"CAMERA", "RECORD_AUDIO", "READ_EXTERNAL_STORAGE"}
    assert set(df["mode"]) == {"allow"}
    assert df.loc[df["op"] == "CAMERA", "duration"].item() == "+420ms"
    assert ["shell", "appops", "get", "com.spy.app"] in adb.calls


def test_recent_permissions_used_is_empty_when_the_app_has_none(fake_bin):
    fake_bin("adb", [{"match": "appops", "stdout": "No operations.\n"}])
    assert perms.recent_permissions_used("com.spy.app").empty


def test_package_info_reads_only_the_requested_package(tmp_path):
    txt = tmp_path / "abc_android.txt"
    txt.write_text(DUMP)
    out = perms.package_info(str(tmp_path / "abc_android.json"), "com.spy.app")
    _, stats = out
    assert stats["firstInstallTime"] == "2024-01-02 03:04:05"
    assert stats["versionName"] == "1.2.3"
