"""Shared test setup.

The application resolves many paths relative to the `sherloc/` directory
(for example `static_data/app-flags.csv`), so tests run from there.
"""

import os
from pathlib import Path

SHERLOC_DIR = Path(__file__).resolve().parent.parent / "sherloc"
os.chdir(SHERLOC_DIR)

# test_parse_dump.py needs a real phone dump that is gitignored. Skip it
# when the fixture is not present so the rest of the suite can run in CI.
_DUMP_FIXTURE = (
    SHERLOC_DIR
    / "phone_dumps"
    / "83c6500a47585595f72d654829cab29edd2c4f5253e6c05d5576cf04661fd6eb_android.txt"
)

collect_ignore = []
if not _DUMP_FIXTURE.exists():
    collect_ignore.append("test_parse_dump.py")


import pytest  # noqa: E402

from tests.fakebin import FakeTool  # noqa: E402


@pytest.fixture
def fake_bin(tmp_path, monkeypatch):
    """Return `make(name, responses)`; the tools are found first on PATH."""
    d = tmp_path / "fakebin"
    d.mkdir()
    monkeypatch.setenv("PATH", f"{d}:" + __import__("os").environ["PATH"])

    def make(name, responses=None):
        return FakeTool(d, name, responses)

    return make
