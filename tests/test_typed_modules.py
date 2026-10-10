"""Modules written for the hardening work are fully typed and checked by mypy.

Older modules are not. Add a module here once its functions have annotations.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TYPED = ["debuglog.py", "inputcheck.py", "clientdata.py", "consultstore.py", "takehome.py", "indicators.py", "scanrecord.py"]


def test_typed_modules_pass_mypy():
    pytest.importorskip("mypy")
    r = subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file", str(ROOT / "mypy.ini"), *TYPED],
        cwd=ROOT / "sherloc",
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_typed_module_exists():
    for name in TYPED:
        assert (ROOT / "sherloc" / name).is_file()
