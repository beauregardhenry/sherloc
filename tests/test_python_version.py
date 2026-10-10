"""Sherloc's minimum Python version is named in several places; they must agree.

Python 3.10 stopped receiving security fixes on 2026-10-01
(https://devguide.python.org/versions/). The minimum is now 3.12.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN = "3.12"


def _read(path):
    return (ROOT / path).read_text()


def test_ci_runs_the_minimum_version():
    for wf in ("tests.yml", "audit.yml", "get-stalkerware-indicators.yml"):
        text = _read(f".github/workflows/{wf}")
        versions = set(re.findall(r'python-version:\s*"?([\d.]+)"?', text))
        versions |= set(v for m in re.findall(r"python-version:\s*\[([^\]]+)\]", text) for v in re.findall(r"[\d.]+", m))
        assert MIN in versions, (wf, versions)
        assert not any(v in ("3.10", "3.11") for v in versions), (wf, versions)


def test_setup_files_name_the_minimum():
    assert f'python@{MIN}' in _read("sherloc/Brewfile")
    assert f"PYTHON_VERSION:='{MIN}'" in _read("sherloc/sherloc.sh")
    assert f"python_version = {MIN}" in _read("mypy.ini")
    assert f"Python {MIN}" in _read("README.md")
    assert f"Python {MIN} or newer" in _read("CONTRIBUTING.md")
    assert "(3, 12)" in _read("dev.sh")


def test_no_file_still_names_python_3_10():
    for path in ("README.md", "CONTRIBUTING.md", "dev.sh", "mypy.ini", "sherloc/sherloc.sh", "sherloc/Brewfile"):
        assert "3.10" not in _read(path), path


def test_the_app_refuses_to_start_on_an_old_python():
    text = _read("sherloc/main.py")
    assert "sys.version_info < (3, 12)" in text
