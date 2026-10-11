"""The spyware check itself: `find_spyapps` and the app details page.

The scan pages call `find_spyapps` with the apps read from the phone. It
flags each app from the bundled blocklist (app-flags.csv), the store it came
from and its name, scores it, and sorts the riskiest first. The other scan
tests replace the scanner with a fake, so these are the tests that run it.
"""

import sqlite3

import pandas as pd
import pytest

import config
from phone_scanner import AndroidScan, IosScan, blocklist

SERIAL = "R58M123ABCD"

# Real entries in static_data/app-flags.csv.
SPYWARE = "com.spy2mobile.light"  # offstore spyware, listed as "Data Backup"
DUAL_USE = "LEM.TrackMe"  # dual-use, "TrackMe - GPS Tracker"
# Not in the list.
REGEX_ONLY = "com.example.keylogger"
PLAIN = "com.example.calculator"
SYSTEM = "com.example.settings"
SIDELOADED = "com.example.sideloaded"


@pytest.fixture
def no_app_info(tmp_path, monkeypatch):
    """A fresh installation: static_data/app-info.db is not in the repository."""
    monkeypatch.setattr(config, "APP_INFO_SQLITE_FILE", f"sqlite:///{tmp_path / 'missing' / 'app-info.db'}")
    return tmp_path / "missing" / "app-info.db"


@pytest.fixture
def app_info(tmp_path, monkeypatch):
    """An app-info.db with Play Store titles, as data_process.py builds it."""
    path = tmp_path / "app-info.db"
    con = sqlite3.connect(path)
    con.execute("create table apps (appid text, title text, description text, permissions text)")
    con.executemany(
        "insert into apps values (?, ?, ?, ?)",
        [
            (PLAIN, "Calculator Pro", "Adds numbers.", "android.permission.INTERNET"),
            (DUAL_USE, "Café Tracker – Family", "Finds phones.", ""),
        ],
    )
    con.commit()
    con.close()
    monkeypatch.setattr(config, "APP_INFO_SQLITE_FILE", f"sqlite:///{path}")
    return path


def android_with(monkeypatch, apps, system=(), offstore=()):
    sc = AndroidScan()
    monkeypatch.setattr(sc, "get_apps", lambda serialno, from_dump=False: list(apps))
    monkeypatch.setattr(sc, "get_system_apps", lambda serialno, from_dump=False: list(system))
    monkeypatch.setattr(sc, "get_offstore_apps", lambda serialno, from_dump=False: list(offstore))
    return sc


ALL = [PLAIN, SPYWARE, REGEX_ONLY, DUAL_USE, SYSTEM, SIDELOADED]


@pytest.fixture
def result(monkeypatch, no_app_info):
    sc = android_with(monkeypatch, ALL, system=[SYSTEM], offstore=[SIDELOADED, SPYWARE])
    return sc.find_spyapps(SERIAL)


# --- flags ------------------------------------------------------------------


def test_listed_spyware_is_flagged(result):
    assert "spyware" in result.loc[SPYWARE, "flags"]


def test_a_spy_word_in_the_id_is_flagged(result):
    assert result.loc[REGEX_ONLY, "flags"] == ["regex-spy"]


def test_listed_dual_use_is_flagged(result):
    assert {"dual-use", "regex-spy"} <= set(result.loc[DUAL_USE, "flags"])


def test_an_app_from_outside_the_store_is_flagged(result):
    assert result.loc[SIDELOADED, "flags"] == ["offstore-app"]
    assert "offstore-app" in result.loc[SPYWARE, "flags"]


def test_a_system_app_is_marked(result):
    assert result.loc[SYSTEM, "flags"] == ["system-app"]


def test_an_ordinary_app_has_no_flags(result):
    assert result.loc[PLAIN, "flags"] == []


def test_a_flag_is_added_only_once():
    # The flags lists come out of a groupby; appending to one must not reach another.
    df = blocklist.app_title_and_flag(
        pd.DataFrame({"appId": [SIDELOADED, PLAIN]}), offstore_apps=[SIDELOADED], system_apps=[]
    ).set_index("appId")
    assert df.loc[SIDELOADED, "flags"] == ["offstore-app"]
    assert df.loc[PLAIN, "flags"] == []


# --- scores and order -------------------------------------------------------


def test_scores_follow_the_weights(result):
    assert result.loc[REGEX_ONLY, "score"] == pytest.approx(0.3)
    assert result.loc[SYSTEM, "score"] == pytest.approx(-0.1)
    assert result.loc[PLAIN, "score"] == 0
    assert result.loc[SPYWARE, "score"] >= 1.0


def test_listed_spyware_outranks_dual_use(monkeypatch, no_app_info):
    # "spyware", the flag app-flags.csv uses, had no weight, so a listed
    # spyware app with a neutral name scored 0 and was not highlighted.
    r = android_with(monkeypatch, ["com.lsdroid.cerberus", "com.example.b"]).find_spyapps(SERIAL)
    assert "spyware" in r.loc["com.lsdroid.cerberus", "flags"]
    assert r.loc["com.lsdroid.cerberus", "score"] >= 1.0


def test_the_riskiest_apps_come_first(result):
    scores = result["score"].tolist()
    assert scores == sorted(scores, reverse=True)
    assert result.index[0] == SPYWARE
    assert result.index[-1] == SYSTEM


def test_ties_are_sorted_by_app_id(monkeypatch, no_app_info):
    sc = android_with(monkeypatch, ["com.example.b", "com.example.a"])
    assert sc.find_spyapps(SERIAL).index.tolist() == ["com.example.a", "com.example.b"]


def test_every_installed_app_is_listed_once(result):
    assert sorted(result.index) == sorted(ALL)


def test_the_columns_are_the_ones_the_pages_read(result):
    assert result.columns.tolist() == ["title", "flags", "score", "html_flags"]


def test_no_apps_gives_an_empty_listing(monkeypatch, no_app_info):
    r = android_with(monkeypatch, []).find_spyapps(SERIAL)
    assert r.empty
    assert r.columns.tolist() == ["title", "flags", "score", "html_flags"]


# --- titles -----------------------------------------------------------------


def test_without_app_info_the_blocklist_titles_are_used(result, no_app_info):
    # app-info.db is gitignored, so a fresh installation has none. The scan
    # used to fail with "no such table: apps".
    assert result.loc[SPYWARE, "title"] == "Data Backup"
    assert result.loc[PLAIN, "title"] == ""


def test_a_missing_app_info_file_is_not_created(result, no_app_info):
    assert not no_app_info.exists()
    assert not no_app_info.parent.exists()


def test_app_info_titles_win_over_the_blocklist(monkeypatch, app_info):
    r = android_with(monkeypatch, [PLAIN, DUAL_USE, SPYWARE]).find_spyapps(SERIAL)
    assert r.loc[PLAIN, "title"] == "Calculator Pro"
    assert r.loc[SPYWARE, "title"] == "Data Backup"


def test_titles_are_reduced_to_ascii(monkeypatch, app_info):
    r = android_with(monkeypatch, [DUAL_USE]).find_spyapps(SERIAL)
    assert r.loc[DUAL_USE, "title"] == "Caf Tracker  Family"


def test_ios_titles_come_from_the_dump(monkeypatch, tmp_path, no_app_info):
    sc = IosScan()
    monkeypatch.setattr(sc, "get_apps", lambda serialno, from_dump=False: [REGEX_ONLY, "com.apple.mobilecal"])
    monkeypatch.setattr(sc, "get_system_apps", lambda serialno, from_dump=False: ["com.apple.mobilecal"])
    titles = pd.DataFrame({"title": ["KeyLog", "MobileCal"]}, index=pd.Index([REGEX_ONLY, "com.apple.mobilecal"], name="appId"))
    monkeypatch.setattr(sc, "app_titles", lambda serialno, apps: titles)
    r = sc.find_spyapps(SERIAL)
    assert r.loc[REGEX_ONLY, "title"] == "KeyLog"
    assert r.loc["com.apple.mobilecal", "flags"] == ["system-app"]


# --- the flags as shown on the scan page --------------------------------------


@pytest.mark.parametrize(
    "flag,css",
    [
        ("spyware", "text-primary"),
        ("offstore-spyware", "text-primary"),
        ("dual-use", "text-warning"),
        ("regex-spy", "text-info"),
        ("system-app", 'class="text-"'),
    ],
)
def test_each_flag_gets_its_colour(flag, css):
    assert css in blocklist.flag_str([flag])


def test_each_flag_explains_itself():
    html = blocklist.flag_str(["regex-spy"])
    assert "contain words like 'spy'" in html
    assert "<abbr" in html


def test_empty_flags_are_skipped():
    assert blocklist.flag_str(["", " "]) == ""
    assert blocklist.flag_str(["spyware", ""]).count("<span") == 1


def test_the_page_html_matches_the_flags(result):
    assert "text-primary" in result.loc[SPYWARE, "html_flags"]
    assert result.loc[PLAIN, "html_flags"] == ""


# --- app details (Android) -------------------------------------------------------

DUMP = """\
DUMP OF SERVICE package
Packages:
  Package [com.example.tracker] (abc123):
    userId=10150
    firstInstallTime=2024-01-02 03:04:05
    lastUpdateTime=2024-02-03 04:05:06
    versionName=1.2.3
    requested permissions:
      android.permission.CAMERA
      android.permission.ACCESS_FINE_LOCATION
      com.example.permission.SECRET
DUMP OF SETTINGS secure
adb_enabled=1
"""

APPOPS = "CAMERA: allow; time=+16m12s788ms ago; duration=+10s237ms\nWAKE_LOCK: allow; time=+2h ago\n"


@pytest.fixture
def android_dump(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DUMP_DIR", tmp_path)
    (tmp_path / f"{config.hmac_serial(SERIAL)}_android.txt").write_text(DUMP)


def test_app_details_list_the_permissions_used(fake_adb, android_dump, no_app_info):
    fake_adb.respond([{"match": "appops get com.example.tracker", "stdout": APPOPS}])
    d, info = AndroidScan().app_details(SERIAL, "com.example.tracker")
    names = [p for p, _ in d["permissions"]]
    assert names == ["Take pictures and videos (CAMERA)", "Access precise location (gps and network-based) (ACCESS_FINE_LOCATION)"]
    assert d["permissions"][1][1] == "Last used: Never"
    assert d["permissions"][0][1].startswith("Last used: 20")


def test_app_details_show_install_time_and_version(fake_adb, android_dump, no_app_info):
    fake_adb.respond([{"match": "appops", "stdout": "No operations.\n"}])
    _, info = AndroidScan().app_details(SERIAL, "com.example.tracker")
    assert info["install_time"] == "2024-01-02 03:04:05"
    assert info["last_updated"] == "2024-02-03 04:05:06"
    assert info["app_version"] == "1.2.3"


def test_app_ops_without_a_readable_name_get_their_own_table(fake_adb, android_dump, no_app_info):
    fake_adb.respond([{"match": "appops", "stdout": APPOPS}])
    d, _ = AndroidScan().app_details(SERIAL, "com.example.tracker")
    assert "WAKE_LOCK" in d["non_hf_permissions_html"]
    assert "CAMERA" not in d["non_hf_permissions_html"]


def test_app_ops_are_read_from_the_scanned_phone(fake_adb, android_dump, no_app_info):
    # Without -s, adb refuses to run when two phones are attached.
    fake_adb.respond([{"match": "appops", "stdout": "No operations.\n"}])
    AndroidScan().app_details(SERIAL, "com.example.tracker")
    assert ["-s", SERIAL, "shell", "appops", "get", "com.example.tracker"] in fake_adb.calls


def test_app_details_use_app_info_when_it_exists(fake_adb, android_dump, app_info):
    fake_adb.respond([{"match": "appops", "stdout": "No operations.\n"}])
    d, _ = AndroidScan().app_details(SERIAL, PLAIN)
    assert d["title"] == "Calculator Pro"
    assert d["descriptionHTML"] == "Adds numbers."


def test_an_app_missing_from_the_dump_has_no_permissions(fake_adb, android_dump, no_app_info):
    fake_adb.respond([{"match": "appops", "stdout": "No operations.\n"}])
    d, info = AndroidScan().app_details(SERIAL, "com.example.notthere")
    assert d["permissions"] == []
    assert info["install_time"] == ""


def test_an_unparseable_package_section_has_no_permissions(fake_adb, tmp_path, monkeypatch, no_app_info):
    # package_info returned a bare [] here, and app_details failed to unpack it.
    from phone_scanner import android_permissions

    monkeypatch.setattr(config, "DUMP_DIR", tmp_path)
    (tmp_path / f"{config.hmac_serial(SERIAL)}_android.txt").write_text(DUMP)

    def broken(text):
        raise AttributeError("rsonlite")

    monkeypatch.setattr(android_permissions, "simpleparse", broken)
    assert android_permissions.package_info(
        str(tmp_path / f"{config.hmac_serial(SERIAL)}_android.json"), "com.example.tracker"
    ) == ([], {})


# --- app details (iOS) ------------------------------------------------------------

IOS_APPS = {
    "com.example.tracker": {
        "ApplicationType": "User",
        "CFBundleIdentifier": "com.example.tracker",
        "CFBundleName": "Tracker",
        "CFBundleExecutable": "Tracker",
        "CFBundleVersion": "2.3",
        "Entitlements": {},
        "NSLocationWhenInUseUsageDescription": "See where you are",
        "NSCameraUsageDescription": "Look up InfoPlist.strings",
    },
}


@pytest.fixture
def ios_scan(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(config, "DUMP_DIR", tmp_path)
    sc = IosScan()
    d = tmp_path / f"{config.hmac_serial(SERIAL)}_ios"
    d.mkdir()
    (d / config.IOS_DUMPFILES["Apps"]).write_text(json.dumps(IOS_APPS))
    (d / config.IOS_DUMPFILES["Info"]).write_text(json.dumps({"DeviceClass": "iPhone", "ProductType": "iPhone99,1",
                                                                "ModelNumber": "M", "RegionInfo": "R", "ProductVersion": "17"}))
    sc._load_dump(SERIAL)
    return sc


def test_ios_app_details_come_from_the_dump(ios_scan, no_app_info):
    d, info = ios_scan.app_details(SERIAL, "com.example.tracker")
    assert d["title"] == "Tracker"
    assert info["App Version"] == "2.3"
    reasons = dict(d["permissions"])
    assert "See where you are" in reasons.values()


def test_ios_placeholder_reasons_are_masked(ios_scan, no_app_info):
    d, _ = ios_scan.app_details(SERIAL, "com.example.tracker")
    assert "[description not available]" in dict(d["permissions"]).values()
    assert not any("InfoPlist.strings" in r for _, r in d["permissions"])


def test_the_ios_dump_is_found_by_the_pseudonymised_serial(no_app_info, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DUMP_DIR", tmp_path)
    sc = IosScan()
    base = tmp_path / f"{config.hmac_serial(SERIAL)}_ios"
    assert sc.dump_path(SERIAL, "Dir") == str(base)
    assert sc.dump_path(SERIAL) == str(base / config.IOS_DUMPFILES["Apps"])
    assert sc.dump_path(SERIAL, "Device_Info") == str(base / config.IOS_DUMPFILES["Info"])
    assert SERIAL not in sc.dump_path(SERIAL)


def test_the_android_dump_is_found_by_the_pseudonymised_serial(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DUMP_DIR", tmp_path)
    assert AndroidScan().dump_path(SERIAL) == str(tmp_path / f"{config.hmac_serial(SERIAL)}_android.json")




# --- the app details page, end to end -------------------------------------------


def test_the_details_page_renders_for_an_app_without_app_info(fake_adb, android_dump, no_app_info):
    import web
    import web.view  # noqa: F401

    fake_adb.respond([{"match": "appops", "stdout": APPOPS}])
    web.app.config.update(TESTING=True)
    r = web.app.test_client().get(f"/details/app/android?appId=com.example.tracker&serial={SERIAL}")
    page = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Take pictures and videos (CAMERA)" in page
    assert "WAKE_LOCK" in page


def test_the_ios_details_page_renders(ios_scan, no_app_info, monkeypatch):
    import web
    import web.view  # noqa: F401

    monkeypatch.setattr("web.view.details.get_device", lambda device: ios_scan)
    web.app.config.update(TESTING=True)
    r = web.app.test_client().get(f"/details/app/ios?appId=com.example.tracker&serial={SERIAL}")
    assert r.status_code == 200
    assert "See where you are" in r.get_data(as_text=True)


def test_each_permission_is_shown_with_when_it_was_last_used(fake_adb, android_dump, no_app_info):
    import web

    fake_adb.respond([{"match": "appops", "stdout": "No operations.\n"}])
    page = web.app.test_client().get(f"/details/app/android?appId=com.example.tracker&serial={SERIAL}").get_data(as_text=True)
    # The template printed each (name, detail) pair as a lower-cased Python tuple.
    assert "&#39;, &#39;last used" not in page.lower()
    assert "<b>Take pictures and videos (CAMERA)</b><br><small>Last used: Never</small>" in page


def test_an_app_title_from_the_phone_is_escaped(ios_scan, no_app_info, monkeypatch):
    # The iOS title is the app's executable name, read from the phone. The
    # page printed it unescaped, so an app could run script in Sherloc.
    import web

    ios_scan.parse_dump.df.loc[0, "CFBundleExecutable"] = "<script>alert(1)</script>"
    monkeypatch.setattr("web.view.details.get_device", lambda device: ios_scan)
    page = web.app.test_client().get(f"/details/app/ios?appId=com.example.tracker&serial={SERIAL}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
