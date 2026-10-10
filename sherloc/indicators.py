"""The list of known stalkerware apps, where it came from and when it changed.

`scripts/get-stalkerware-indicators.py` adds apps from the
AssoEchap/stalkerware-indicators repository to `static_data/app-flags.csv`
and records the source and dates in `static_data/app-flags-source.json`. The
app shows that record so a consultant can tell how current the list is.
"""

import csv
import json
import subprocess
from datetime import date
from typing import Any, Optional

import yaml

import config

SOURCE_NAME = "AssoEchap/stalkerware-indicators"
SOURCE_URL = "https://github.com/AssoEchap/stalkerware-indicators"
# The flags that make an app count as known (see phone_scanner/blocklist.py).
FLAGGED = {"dual-use", "spyware", "co-occurrence"}


def read_ioc(path: str) -> list[dict[str, Any]]:
    """Read ioc.yaml. Only plain YAML is accepted, never Python objects."""
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list) or not all(isinstance(e, dict) for e in data):
        raise ValueError("ioc.yaml must be a list of entries.")
    return data


def new_rows(ioc: list[dict[str, Any]], known: set[str]) -> list[list[str]]:
    """Rows for the apps in `ioc` that are not in `known`, each listed once."""
    seen = set(known)
    rows = []
    for element in ioc:
        names = " / ".join(element.get("names") or [])
        for app in element.get("packages") or []:
            if app in seen:
                continue
            seen.add(app)
            rows.append([app, "playstore", "spyware", names])
    return rows


def upstream_info(repo_dir: str) -> dict[str, str]:
    """The commit that was checked out in `repo_dir` and its date, or {}."""

    def git(*args: str) -> str:
        r = subprocess.run(
            ["git", "-C", repo_dir, *args], capture_output=True, text=True, timeout=30
        )
        return r.stdout.strip() if r.returncode == 0 else ""

    commit = git("rev-parse", "HEAD")
    day = git("log", "-1", "--format=%cs")
    if not commit or not day:
        return {}
    return {"commit": commit, "date": day}


def write_source_file(
    path: str, *, commit: str, upstream_date: str, changed: str, added: int
) -> None:
    record = {
        "source": SOURCE_NAME,
        "url": SOURCE_URL,
        "commit": commit,
        "upstream_date": upstream_date,
        "changed": changed,
        "added": added,
    }
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
        f.write("\n")


def _count_flagged() -> int:
    try:
        with open(config.APP_FLAGS_FILE, newline="", encoding="latin1") as f:
            return sum(1 for row in csv.DictReader(f) if row.get("flag") in FLAGGED)
    except OSError:
        return 0


def summary() -> dict[str, Any]:
    """What the app knows about its list: size, source and dates."""
    out: dict[str, Any] = {"recorded": False, "count": _count_flagged()}
    try:
        with open(config.IOC_SOURCE_FILE) as f:
            rec = json.load(f)
        if isinstance(rec, dict) and rec.get("source") and rec.get("changed"):
            out.update(
                recorded=True,
                source=str(rec["source"]),
                url=str(rec.get("url", "")),
                commit=str(rec.get("commit", ""))[:7],
                upstream_date=str(rec.get("upstream_date", "")),
                changed=str(rec["changed"]),
            )
    except (OSError, ValueError):
        pass
    return out


def describe(s: dict[str, Any]) -> str:
    """One plain sentence for the page and the report."""
    base = f"Stalkerware app list: {s['count']:,} apps."
    if not s["recorded"]:
        return base + " The source and date of the list are not recorded."
    detail = f"Last changed {s['changed']} from {s['source']}"
    extra = [x for x in (f"their data of {s['upstream_date']}" if s["upstream_date"] else "",
                         f"commit {s['commit']}" if s["commit"] else "") if x]
    if extra:
        detail += " (" + ", ".join(extra) + ")"
    return f"{base} {detail}."


def today() -> str:
    return date.today().isoformat()


def update_list(ioc_path: str, flags_path: str, repo_dir: str, source_path: str) -> int:
    """Add new apps from ioc.yaml to the flags file and record the source.

    Returns the number of apps added. Nothing is rewritten when there is
    nothing new, so a quiet week makes no change to commit.
    """
    ioc = read_ioc(ioc_path)
    with open(flags_path, newline="") as f:
        known = {row[0] for row in csv.reader(f) if row}
    rows = new_rows(ioc, known)
    info: Optional[dict[str, str]] = upstream_info(repo_dir)
    if rows:
        with open(flags_path, "rb+") as f:
            # Start on a new line if the file does not end with one.
            f.seek(0, 2)
            if f.tell() and (f.seek(-1, 2), f.read(1))[1] != b"\n":
                f.write(b"\n")
        with open(flags_path, "a", newline="") as f:
            csv.writer(f, lineterminator="\n").writerows(rows)
    if rows and info:
        write_source_file(
            source_path,
            commit=info["commit"],
            upstream_date=info["date"],
            changed=today(),
            added=len(rows),
        )
    return len(rows)
