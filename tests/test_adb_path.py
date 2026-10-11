"""Which adb Sherloc runs.

Android Studio sets ANDROID_HOME to the SDK folder, where adb is in
platform-tools/. Sherloc used ANDROID_HOME/adb, which does not exist there, so
it failed even though `adb` worked in the terminal.
"""

import os
import subprocess
import sys
from pathlib import Path

SHERLOC = Path(__file__).resolve().parent.parent / "sherloc"


def _adb(env_extra):
    env = {k: v for k, v in os.environ.items() if k not in ("ANDROID_HOME", "SHERLOC_ADB")}
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", "import config; print(config.ADB_PATH)"],
        cwd=SHERLOC, env=env, capture_output=True, text=True, check=True,
    ).stdout.strip()


def _tool(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return str(path)


def test_without_android_home_adb_is_found_on_the_path():
    assert _adb({}) == "adb"


def test_the_sdk_layout_is_used(tmp_path):
    adb = _tool(tmp_path / "platform-tools" / "adb")
    assert _adb({"ANDROID_HOME": str(tmp_path)}) == adb


def test_adb_directly_in_android_home_still_works(tmp_path):
    adb = _tool(tmp_path / "adb")
    assert _adb({"ANDROID_HOME": str(tmp_path)}) == adb


def test_an_android_home_without_adb_falls_back_to_the_path(tmp_path):
    assert _adb({"ANDROID_HOME": str(tmp_path)}) == "adb"


def test_sherloc_adb_names_the_program_outright(tmp_path):
    adb = _tool(tmp_path / "custom" / "adb")
    _tool(tmp_path / "platform-tools" / "adb")
    assert _adb({"ANDROID_HOME": str(tmp_path), "SHERLOC_ADB": adb}) == adb
