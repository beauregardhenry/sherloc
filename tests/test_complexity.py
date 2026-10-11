"""No function grows past a cyclomatic complexity of 12 (ruff rule C901).

`app_details` and the manual-add page were split to get under it. Split a
function rather than raising the limit.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 12


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff is not installed")
def test_no_function_is_too_complex():
    r = subprocess.run(
        ["ruff", "check", "--isolated", "--select", "C901", "--config", f"lint.mccabe.max-complexity={LIMIT}",
         "--no-cache", "--output-format", "concise", "sherloc"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
