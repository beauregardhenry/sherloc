"""All client data lives under one folder, set by SHERLOC_DATA_DIR.

That is step 2 of the RAM-only plan: point the setting at a RAM disk and
nothing about the client reaches the hard drive. Without the setting the
folders stay where earlier versions put them.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SHERLOC = Path(__file__).resolve().parent.parent / "sherloc"

PROBE = """
import json, config, evidence_choices
print(json.dumps({
    "root": str(config.DATA_ROOT),
    "dirs": [str(d) for d in config.client_data_dirs()],
    "db": config.SQL_DB_PATH,
    "log": str(config.LOG_DIR),
    "report_path": str(config.REPORT_PATH),
    "consult_store_dir": str(evidence_choices.TMP_CONSULT_DATA_DIR),
}))
"""


def _probe(env_extra):
    env = {k: v for k, v in os.environ.items() if k not in ("SHERLOC_DATA_DIR", "TEST")}
    env.update(env_extra)
    out = subprocess.run(
        [sys.executable, "-c", PROBE], cwd=SHERLOC, env=env,
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def _under(path, root):
    path = os.path.realpath(path.replace("sqlite:///", "").replace("~test", ""))
    root = os.path.realpath(root)
    return os.path.commonpath([path, root]) == root


def test_every_client_data_location_is_under_the_setting(tmp_path):
    root = tmp_path / "ramdisk"
    got = _probe({"SHERLOC_DATA_DIR": str(root)})
    assert os.path.realpath(got["root"]) == os.path.realpath(root)
    places = got["dirs"] + [got["db"], got["log"], got["report_path"],
                            got["consult_store_dir"]]
    assert all(_under(p, str(root)) for p in places), places


def test_without_the_setting_the_folders_stay_where_they_were():
    got = _probe({})
    assert os.path.realpath(got["root"]) == os.path.realpath(SHERLOC)
    assert got["db"] == f"sqlite:///{SHERLOC / 'data' / 'fieldstudy.db'}"
    assert [Path(d).relative_to(SHERLOC).as_posix() for d in got["dirs"]] == [
        "phone_dumps", "webstatic/images/screenshots", "reports", "tmp-consult-data", "data",
    ]


def test_test_mode_still_uses_its_own_database(tmp_path):
    got = _probe({"SHERLOC_DATA_DIR": str(tmp_path), "TEST": "1"})
    assert got["db"] == f"sqlite:///{tmp_path / 'data' / 'fieldstudy.db'}~test"


# Folder and file names of client data. Outside config.py, code must reach
# them through config, or they land outside SHERLOC_DATA_DIR.
CLIENT_DATA_NAMES = {"phone_dumps", "tmp-consult-data", "screenshots", "reports", "data"}


def _names_client_data(value):
    if value.startswith("/"):  # a URL route, not a file
        return False
    parts = value.replace("\\", "/").split("/")
    return any(p in CLIENT_DATA_NAMES or p.startswith("fieldstudy") for p in parts)


def _string_constants(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node


def test_no_client_data_path_is_written_out_by_hand():
    found = []
    for path in SHERLOC.rglob("*.py"):
        rel = path.relative_to(SHERLOC).as_posix()
        if rel == "config.py" or rel.startswith(("scripts/", "static_data/")):
            continue
        tree = ast.parse(path.read_text())
        main_blocks = [
            n for n in tree.body
            if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test)
        ]
        skip = {id(c) for b in main_blocks for c in ast.walk(b)}
        for node in _string_constants(tree):
            if id(node) in skip:
                continue
            if _names_client_data(node.value):
                found.append(f"{rel}:{node.lineno}: {node.value!r}")
    assert found == []


def test_screenshots_are_found_under_the_configured_folder(tmp_path, monkeypatch):
    import config
    from evidence_accounts import get_all_screenshot_files

    shots = tmp_path / "shots"
    (shots / "HSN_abc" / "rooting").mkdir(parents=True)
    (shots / "HSN_abc" / "rooting" / "1.png").write_bytes(b"png")
    monkeypatch.setattr(config, "SCREENSHOT_DIR", shots)
    files = get_all_screenshot_files()
    assert files["devices"]["HSN_abc"]["root"] == [str(shots / "HSN_abc" / "rooting" / "1.png")]


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    import config
    import web
    import web.view

    shots = tmp_path / "shots"
    shots.mkdir()
    monkeypatch.setattr(config, "SCREENSHOT_DIR", shots)
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return web.app.test_client(), shots


def test_a_screenshot_outside_webstatic_is_served(app_client):
    client, shots = app_client
    (shots / "HSN_abc" / "rooting").mkdir(parents=True)
    f = shots / "HSN_abc" / "rooting" / "1.png"
    f.write_bytes(b"\x89PNG-test")
    import web

    url = web.app.jinja_env.filters["screenshot_path"](str(f))
    r = client.get("/" + url)
    assert r.status_code == 200
    assert r.data == b"\x89PNG-test"


def test_the_screenshot_route_does_not_leave_its_folder(app_client, tmp_path):
    client, _ = app_client
    (tmp_path / "secret.txt").write_text("no")
    assert client.get("/client-screenshots/../secret.txt").status_code == 404


def test_deleting_a_screenshot_only_touches_the_screenshot_folder(app_client, tmp_path):
    client, shots = app_client
    outside = tmp_path / "keep.txt"
    outside.write_text("keep")
    (shots / "HSN_abc" / "rooting").mkdir(parents=True)
    inside = shots / "HSN_abc" / "rooting" / "1.png"
    inside.write_bytes(b"png")
    client.post("/evidence/screenshots", data={
        "root_screenshots-0-fname": str(outside),
        "root_screenshots-0-delete": "y",
        "root_screenshots-1-fname": str(inside),
        "root_screenshots-1-delete": "y",
    })
    assert outside.exists()
    assert not inside.exists()


LAUNCHER = SHERLOC / "sherloc.sh"


def test_the_launcher_passes_the_setting_through_sudo(tmp_path):
    """sudo clears the environment. Without a pass-through, SHERLOC_DATA_DIR
    would be dropped and client data would go to the hard drive."""
    text = LAUNCHER.read_text()
    assert "sudo $PYTHON" not in text
    block = text[text.index("# sudo clears the environment"):]
    block = block[: block.index("\ndone\n") + 6]
    out = subprocess.run(
        ["bash", "-c", block + 'printf "%s\\n" ${SHERLOC_ENV[@]+"${SHERLOC_ENV[@]}"}'],
        env={"PATH": os.environ["PATH"], "SHERLOC_DATA_DIR": str(tmp_path / "ram disk")},
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    assert out == [f"SHERLOC_DATA_DIR={tmp_path / 'ram disk'}"]


def test_the_app_says_where_client_data_goes():
    assert "config.DATA_ROOT" in (SHERLOC / "main.py").read_text()
