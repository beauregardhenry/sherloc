"""The app list is updated from stalkerware-indicators, and the app shows where
the list came from and when it last changed.
"""

import csv
import json
import subprocess
from datetime import date

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
import indicators

IOC = [
    {"name": "Alpha", "names": ["Alpha Spy", "Alpha Tracker"], "packages": ["com.alpha.spy", "com.alpha.two"]},
    {"name": "Beta", "packages": ["com.beta"]},
    {"name": "NoPackages", "names": ["x"]},
    {"name": "Again", "names": ["Alpha again"], "packages": ["com.alpha.spy"]},
]


# --- merging ----------------------------------------------------------------


def test_new_apps_become_spyware_rows():
    rows = indicators.new_rows(IOC, known={"com.alpha.two"})
    assert ["com.alpha.spy", "playstore", "spyware", "Alpha Spy / Alpha Tracker"] in rows
    assert ["com.beta", "playstore", "spyware", ""] in rows


def test_known_apps_are_not_added_again():
    rows = indicators.new_rows(IOC, known={"com.alpha.two"})
    assert "com.alpha.two" not in [r[0] for r in rows]


def test_an_app_listed_twice_in_one_update_is_added_once():
    rows = indicators.new_rows(IOC, known=set())
    ids = [r[0] for r in rows]
    assert ids.count("com.alpha.spy") == 1


def test_entries_without_packages_are_skipped():
    assert indicators.new_rows([{"name": "n", "names": ["x"]}], known=set()) == []


def test_read_ioc_rejects_a_file_that_is_not_a_list(tmp_path):
    f = tmp_path / "ioc.yaml"
    f.write_text("key: value\n")
    with pytest.raises(ValueError):
        indicators.read_ioc(str(f))


def test_read_ioc_does_not_run_yaml_tags(tmp_path):
    f = tmp_path / "ioc.yaml"
    f.write_text("- !!python/object/apply:os.getcwd []\n")
    with pytest.raises(Exception):
        indicators.read_ioc(str(f))


def test_read_ioc_reads_a_list(tmp_path):
    f = tmp_path / "ioc.yaml"
    f.write_text("- name: A\n  packages: [com.a]\n")
    assert indicators.read_ioc(str(f)) == [{"name": "A", "packages": ["com.a"]}]


# --- where the data came from ------------------------------------------------


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_upstream_info_reads_the_commit_and_its_date(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "ioc.yaml").write_text("[]\n")
    _git(tmp_path, "add", "ioc.yaml")
    env = {"GIT_AUTHOR_DATE": "2026-09-28T10:00:00", "GIT_COMMITTER_DATE": "2026-09-28T10:00:00"}
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@example.com",
         "commit", "-q", "-m", "x"],
        check=True, capture_output=True, env={**__import__("os").environ, **env},
    )
    info = indicators.upstream_info(str(tmp_path))
    assert len(info["commit"]) == 40
    assert info["date"] == "2026-09-28"


def test_upstream_info_without_a_git_repo_is_empty(tmp_path):
    assert indicators.upstream_info(str(tmp_path)) == {}


def test_source_file_round_trip(tmp_path):
    f = tmp_path / "src.json"
    indicators.write_source_file(
        str(f), commit="a" * 40, upstream_date="2026-09-28", changed="2026-10-04", added=26
    )
    data = json.loads(f.read_text())
    assert data["source"] == "AssoEchap/stalkerware-indicators"
    assert data["url"] == "https://github.com/AssoEchap/stalkerware-indicators"
    assert data["commit"] == "a" * 40
    assert data["changed"] == "2026-10-04"
    assert data["added"] == 26


# --- what the app shows ------------------------------------------------------


@pytest.fixture
def listing(tmp_path, monkeypatch):
    flags = tmp_path / "flags.csv"
    with open(flags, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["appId", "store", "flag", "title"])
        w.writerow(["a", "playstore", "spyware", ""])
        w.writerow(["b", "playstore", "dual-use", ""])
        w.writerow(["c", "playstore", "safe", ""])
    monkeypatch.setattr(config, "APP_FLAGS_FILE", str(flags))
    src = tmp_path / "src.json"
    monkeypatch.setattr(config, "IOC_SOURCE_FILE", str(src))
    return src


def test_summary_counts_the_apps_that_are_flagged(listing):
    assert indicators.summary()["count"] == 2


def test_summary_without_a_source_file_says_it_is_not_recorded(listing):
    s = indicators.summary()
    assert s["recorded"] is False
    assert "not recorded" in indicators.describe(s)


def test_summary_with_a_source_file_names_source_and_dates(listing):
    indicators.write_source_file(
        str(listing), commit="1a2b3c4d" + "0" * 32, upstream_date="2026-09-28", changed="2026-10-04", added=3
    )
    s = indicators.summary()
    text = indicators.describe(s)
    assert s["recorded"] is True
    for part in ("AssoEchap/stalkerware-indicators", "2026-10-04", "2026-09-28", "1a2b3c4"):
        assert part in text
    assert "1a2b3c4d0" not in text  # the short hash only


def test_a_damaged_source_file_counts_as_not_recorded(listing):
    listing.write_text("{not json")
    assert indicators.summary()["recorded"] is False


def test_the_home_page_shows_the_list_source(listing):
    indicators.write_source_file(
        str(listing), commit="1a2b3c4d" + "0" * 32, upstream_date="2026-09-28", changed="2026-10-04", added=3
    )
    web.app.config.update(TESTING=True)
    r = web.app.test_client().get("/privacy", headers={"Host": "localhost:6200"})
    body = r.get_data(as_text=True)
    assert "AssoEchap/stalkerware-indicators" in body
    assert "2026-10-04" in body


# --- the whole update ---------------------------------------------------------


@pytest.fixture
def update_env(tmp_path, monkeypatch):
    repo = tmp_path / "ioc-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "ioc.yaml").write_text(
        "- names: [Alpha]\n  packages: [com.alpha, com.known]\n- packages: [com.beta]\n"
    )
    _git(repo, "add", "ioc.yaml")
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "x"],
        check=True, capture_output=True,
    )
    flags = tmp_path / "flags.csv"
    flags.write_text("appId,store,flag,title\ncom.known,playstore,spyware,Known\n")
    return repo, flags, tmp_path / "src.json"


def test_update_adds_new_apps_and_records_the_source(update_env):
    repo, flags, src = update_env
    added = indicators.update_list(str(repo / "ioc.yaml"), str(flags), str(repo), str(src))
    assert added == 2
    lines = flags.read_text().splitlines()
    assert lines[0] == "appId,store,flag,title"
    assert "com.alpha,playstore,spyware,Alpha" in lines
    assert "com.beta,playstore,spyware," in lines
    rec = json.loads(src.read_text())
    assert rec["added"] == 2
    assert rec["changed"] == date.today().isoformat()
    assert len(rec["commit"]) == 40


def test_a_second_update_with_nothing_new_changes_nothing(update_env):
    repo, flags, src = update_env
    indicators.update_list(str(repo / "ioc.yaml"), str(flags), str(repo), str(src))
    before = (flags.read_text(), src.read_text())
    assert indicators.update_list(str(repo / "ioc.yaml"), str(flags), str(repo), str(src)) == 0
    assert (flags.read_text(), src.read_text()) == before


def test_the_full_report_states_the_list_version_and_the_take_home_copy_does_not():
    import evidence_collection as ec
    from tests.test_printout import _context

    line = "Stalkerware app list: 5 apps. Last changed 2026-10-04 from AssoEchap/stalkerware-indicators."
    full = ec.render_printout_html(_context(indicator_list=line))
    assert "Last changed 2026-10-04 from AssoEchap/stalkerware-indicators" in full
    home = ec.render_printout_html(_context(indicator_list=line, takehome=True))
    assert "AssoEchap" not in home
