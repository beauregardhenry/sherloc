"""Sherloc supports Apple Silicon Macs. Intel Macs are not supported: there,
Homebrew builds Pango (which the PDF report needs) from source, slowly and
often unsuccessfully."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "sherloc" / "sherloc.sh"


def test_the_readme_names_apple_silicon_as_the_supported_mac():
    text = (ROOT / "README.md").read_text()
    assert "Apple Silicon" in text
    assert "Intel Macs are not supported" in text


def _warning_for(system, machine):
    text = LAUNCHER.read_text()
    block = text[text.index("# Intel Macs are not supported"):]
    block = block[: block.index("\nfi\n") + 4]
    script = f'uname() {{ case "$1" in -s) echo {system};; -m) echo {machine};; esac; }}\n' + block
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout


def test_the_launcher_warns_on_an_intel_mac():
    assert "Intel Macs are not supported" in _warning_for("Darwin", "x86_64")


def test_the_launcher_is_quiet_on_apple_silicon_and_linux():
    assert _warning_for("Darwin", "arm64") == ""
    assert _warning_for("Linux", "x86_64") == ""
