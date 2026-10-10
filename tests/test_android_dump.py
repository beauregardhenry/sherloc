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


def test_recent_permissions_used_reads_appops_output(fake_adb):
    adb = fake_adb
    adb.respond([{"match": "appops get com.spy.app", "stdout": APPOPS}])
    df = perms.recent_permissions_used("com.spy.app")
    assert set(df["op"]) == {"CAMERA", "RECORD_AUDIO", "READ_EXTERNAL_STORAGE"}
    assert set(df["mode"]) == {"allow"}
    assert df.loc[df["op"] == "CAMERA", "duration"].item() == "+420ms"
    assert ["shell", "appops", "get", "com.spy.app"] in adb.calls


def test_recent_permissions_used_is_empty_when_the_app_has_none(fake_adb):
    fake_adb.respond([{"match": "appops", "stdout": "No operations.\n"}])
    assert perms.recent_permissions_used("com.spy.app").empty


def test_package_info_reads_only_the_requested_package(tmp_path):
    txt = tmp_path / "abc_android.txt"
    txt.write_text(DUMP)
    out = perms.package_info(str(tmp_path / "abc_android.json"), "com.spy.app")
    _, stats = out
    assert stats["firstInstallTime"] == "2024-01-02 03:04:05"
    assert stats["versionName"] == "1.2.3"


HOSTILE_APPIDS = ["x' ; touch {marker} ; '", "$(touch {marker})", "`touch {marker}`", "a b", "a;b"]


@pytest.mark.parametrize("appid", HOSTILE_APPIDS)
def test_package_info_never_runs_text_from_the_app_id(tmp_path, appid):
    marker = tmp_path / "pwned"
    (tmp_path / "abc_android.txt").write_text(DUMP)
    with pytest.raises(ValueError):
        perms.package_info(str(tmp_path / "abc_android.json"), appid.format(marker=marker))
    assert not marker.exists()


@pytest.mark.parametrize("appid", HOSTILE_APPIDS)
def test_recent_permissions_never_run_text_from_the_app_id(fake_adb, tmp_path, appid):
    marker = tmp_path / "pwned"
    adb = fake_adb
    with pytest.raises(ValueError):
        perms.recent_permissions_used(appid.format(marker=marker))
    assert not marker.exists()
    assert adb.calls == []


def test_package_info_for_an_app_missing_from_the_dump_is_empty(tmp_path):
    (tmp_path / "abc_android.txt").write_text(DUMP)
    assert perms.package_info(str(tmp_path / "abc_android.json"), "com.nothere") == ([], {})


# --- the last package, and sections that follow a package ---------------------
# A package's section used to run to the next "Package [" line or the end of
# the file. For the last package that took in the next section at a lower
# indent, and rsonlite raised IndentationError.


def test_package_info_for_the_last_package_in_the_dump(tmp_path):
    (tmp_path / "abc_android.txt").write_text(DUMP)
    _, stats = perms.package_info(str(tmp_path / "abc_android.json"), "com.other")
    assert stats["firstInstallTime"] == "2023-05-06 07:08:09"


def test_package_info_stops_at_a_section_that_follows_the_package(tmp_path):
    dump = DUMP.replace(
        "DUMP OF SETTINGS secure",
        "Queries:\n  system apps queryable: false\nDUMP OF SETTINGS secure",
    )
    (tmp_path / "abc_android.txt").write_text(dump)
    _, stats = perms.package_info(str(tmp_path / "abc_android.json"), "com.other")
    assert stats["firstInstallTime"] == "2023-05-06 07:08:09"
    assert "system apps queryable" not in stats


# --- data usage ----------------------------------------------------------------
# Columns of /proc/net/xt_qtaguid/stats, with spaces turned into commas as the
# old scan script did. Not recorded from a device; follows the kernel's header.
QTAGUID_HEADER = (
    "idx,iface,acct_tag_hex,uid_tag_int,cnt_set,rx_bytes,rx_packets,tx_bytes,tx_packets,"
    "rx_tcp_bytes,rx_tcp_packets,rx_udp_bytes,rx_udp_packets,rx_other_bytes,rx_other_packets,"
    "tx_tcp_bytes,tx_tcp_packets,tx_udp_bytes,tx_udp_packets,tx_other_bytes,tx_other_packets"
)


def _row(idx, uid, cnt_set, rx, tx):
    return f"{idx},wlan0,0x0,{uid},{cnt_set},{rx},1,{tx},1" + ",0" * 12


def test_data_usage_adds_up_foreground_and_background_for_the_uid():
    mb = 1024 * 1024
    d = {"net_stats": [QTAGUID_HEADER, _row(2, 10150, 1, mb, mb), _row(3, 10150, 0, mb, 0), _row(4, 999, 1, 50 * mb, 0)]}
    assert parse_dump.AndroidDump.get_data_usage(d, "10150") == {"foreground": "2.00 MB", "background": "1.00 MB"}


def test_data_usage_skips_a_line_with_an_extra_field():
    # "Expected 21 fields in line 556, saw 22" was seen on a real device.
    mb = 1024 * 1024
    d = {"net_stats": [QTAGUID_HEADER, _row(2, 10150, 1, mb, 0), _row(3, 10150, 1, mb, 0) + ",9"]}
    assert parse_dump.AndroidDump.get_data_usage(d, "10150")["foreground"] == "1.00 MB"


def test_data_usage_with_empty_net_stats_is_unknown():
    assert parse_dump.AndroidDump.get_data_usage({"net_stats": []}, "10150") == {
        "foreground": "unknown",
        "background": "unknown",
    }


def test_data_usage_with_unexpected_columns_is_unknown():
    d = {"net_stats": ["a,b,c", "1,2,3"]}
    assert parse_dump.AndroidDump.get_data_usage(d, "10150")["foreground"] == "unknown"
