"""Imports are sorted the way `ruff check --fix` sorts them (rule I001).

ruff.toml at the repository root tells ruff that the modules under sherloc/
and tests/ are this project's own, so they sort after third-party ones.
Fix a finding with:

    ruff check --select I001 --fix sherloc tests
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff is not installed")
def test_imports_are_sorted():
    r = subprocess.run(
        ["ruff", "check", "--select", "I001", "--no-cache", "--output-format", "concise", "sherloc", "tests"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


SHERLOC = ROOT / "sherloc"


@pytest.mark.parametrize("first", ["evidence_collection", "web.view.details", "web.view.scan", "scanflow"])
def test_modules_import_in_any_order(first):
    # Sorting put these before `import web` and exposed circular imports.
    r = subprocess.run(
        [sys.executable, "-c", f"import {first}; import web; import web.view"],
        cwd=SHERLOC, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr[-2000:]


def test_only_views_import_from_the_views():
    offenders = [
        p.relative_to(SHERLOC).as_posix()
        for p in SHERLOC.rglob("*.py")
        if "web/view" not in p.as_posix() and p.name != "__init__.py"
        and ("from web.view" in p.read_text() or "import web.view" in p.read_text())
    ]
    assert offenders == []


def test_the_project_modules_are_first_party():
    config = (ROOT / "ruff.toml").read_text()
    assert 'src = ["sherloc", "."]' in config
