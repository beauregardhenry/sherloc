"""CONTRIBUTING.md names files and commands; they must exist."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = (ROOT / "CONTRIBUTING.md").read_text()


def test_every_file_named_in_contributing_exists():
    named = re.findall(r"`([\w./-]+\.(?:py|json|txt|yml|md|sh))`", TEXT)
    assert named
    missing = [n for n in named if not (ROOT / n).exists()]
    assert not missing, missing


def test_dev_script_is_executable_and_documented():
    assert (ROOT / "dev.sh").stat().st_mode & 0o111
    assert "./dev.sh" in TEXT
