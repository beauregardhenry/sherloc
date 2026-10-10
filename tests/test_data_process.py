"""phone_scanner/data_process.py rebuilds app-flags.csv and app-info.db from
app-store crawls. It is run by hand, rarely, and no test ran it before; it
had stopped working (it read `config.SPYWARE_LIST_FILE`, which does not
exist). These tests run it on three tiny crawl files.
"""

import sqlite3

import pandas as pd
import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
from phone_scanner import data_process


@pytest.fixture
def crawl(tmp_path, monkeypatch):
    play = tmp_path / "play.csv"
    pd.DataFrame(
        {"appId": ["com.dual.one", "com.dual.two", "com.calc"],
         "title": ["Dual One", "Dual Two", "Calculator"],
         "ml_score": [0.9, 0.8, 0.1],
         "Permissions List": ["a", "b", "c"]}
    ).to_csv(play, index=False)
    apple = tmp_path / "apple.csv"
    pd.DataFrame(
        {"appId": ["com.ios.track", "com.ios.game"], "title": ["Tracker", "Game"],
         "relevant": ["y", "n"]}
    ).to_csv(apple, index=False)
    off = tmp_path / "off.csv"
    pd.DataFrame({"appId": ["com.off.spy"], "title": ["Off Spy"]}).to_csv(off, index=False)
    spy = tmp_path / "spyware.csv"
    pd.DataFrame({"appId": ["com.dual.two"]}).to_csv(spy, index=False)

    monkeypatch.setattr(config, "source_files", {"playstore": str(play), "appstore": str(apple), "offstore": str(off)})
    monkeypatch.setattr(config, "spyware_list_file", str(spy))
    monkeypatch.setattr(config, "APP_FLAGS_FILE", str(tmp_path / "app-flags.csv"))
    monkeypatch.setattr(config, "APP_INFO_SQLITE_FILE", f"sqlite:///{tmp_path / 'app-info.db'}")
    return tmp_path


def test_app_flags_file_keeps_relevant_apps_with_their_flags(crawl):
    data_process.create_app_flags_file()
    flags = pd.read_csv(crawl / "app-flags.csv", index_col="appId")
    assert set(flags.index) == {"com.dual.one", "com.dual.two", "com.ios.track", "com.off.spy"}
    assert flags.loc["com.dual.one", "flag"] == "dual-use"
    assert flags.loc["com.off.spy", "flag"] == "spyware"
    # The hand-picked spyware list overrides the crawl's flag.
    assert flags.loc["com.dual.two", "flag"] == "spyware"
    assert flags.loc["com.ios.track", "store"] == "appstore"


def test_app_info_database_has_every_app_and_an_index(crawl):
    data_process.create_app_info_dict()
    con = sqlite3.connect(crawl / "app-info.db")
    try:
        ids = {r[0] for r in con.execute("select appId from apps")}
        indexes = {r[0] for r in con.execute("select name from sqlite_master where type='index'")}
        columns = {r[1] for r in con.execute("pragma table_info(apps)")}
    finally:
        con.close()
    assert ids == {"com.dual.one", "com.dual.two", "com.calc", "com.ios.track", "com.ios.game", "com.off.spy"}
    assert "idx_appId" in indexes
    # Column names are normalised: "Permissions List" -> "permissions_list".
    assert "permissions_list" in columns


def test_join_csv_files(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    pd.DataFrame({"appId": ["x"]}).to_csv(a, index=False)
    pd.DataFrame({"appId": ["y"]}).to_csv(b, index=False)
    out = tmp_path / "out.csv.gz"
    data_process.join_csv_files([a, b], out)
    assert list(pd.read_csv(out)["appId"]) == ["x", "y"]
