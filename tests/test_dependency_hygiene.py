"""Dependencies are kept current and audited.

`pip-audit` found known vulnerabilities in two pinned packages. These tests
keep the fixes in place and keep the automation that finds the next ones.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "sherloc" / "requirements.txt"
WORKFLOWS = ROOT / ".github" / "workflows"


def _pins():
    pins = {}
    for line in REQUIREMENTS.read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==([\w.]+)\s*$", line.strip())
        if m:
            pins[m.group(1).lower()] = tuple(int(p) for p in m.group(2).split(".") if p.isdigit())
    return pins


def test_filelock_is_gone_or_has_the_symlink_race_fixes():
    # No code uses filelock since the consultation answers moved to SQLite.
    # If it comes back: GHSA-w853-jp5j-5j7f (fixed in 3.20.1) and
    # GHSA-qmgc-5h2g-mvrw (fixed in 3.20.3).
    pin = _pins().get("filelock")
    assert pin is None or pin >= (3, 20, 3)


def test_every_pinned_package_that_is_only_ours_is_imported_somewhere():
    # A pin nothing uses still has to be audited and updated. filelock was one.
    code = "\n".join(p.read_text() for p in (ROOT / "sherloc").rglob("*.py"))
    for name in ("filelock",):
        if name in _pins():
            assert re.search(rf"^\s*(import|from) {name}\b", code, re.M), f"{name} is pinned but unused"


def test_dependabot_watches_actions_and_python_packages():
    cfg = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text())
    assert cfg["version"] == 2
    ecosystems = {u["package-ecosystem"]: u for u in cfg["updates"]}
    assert {"github-actions", "pip"} <= set(ecosystems)
    assert ecosystems["pip"]["directory"] == "/sherloc"
    for u in ecosystems.values():
        assert u["schedule"]["interval"] in {"daily", "weekly", "monthly"}


def test_a_workflow_audits_the_requirements():
    texts = [p.read_text() for p in WORKFLOWS.glob("*.y*ml")]
    audit = [t for t in texts if "pip-audit" in t]
    assert audit, "no workflow runs pip-audit"
    assert any("sherloc/requirements.txt" in t for t in audit)


def test_the_audit_runs_on_a_schedule_and_on_pull_requests():
    for p in WORKFLOWS.glob("*.y*ml"):
        text = p.read_text()
        if "pip-audit" in text:
            on = yaml.safe_load(text)[True]  # YAML reads the key `on` as True
            assert "schedule" in on and "pull_request" in on
            return
    raise AssertionError("no audit workflow")


def test_every_ignored_advisory_says_why():
    # An ignored advisory hides a real finding, so each needs a comment above it.
    for p in WORKFLOWS.glob("*.y*ml"):
        lines = p.read_text().splitlines()
        for i, line in enumerate(lines):
            if "--ignore-vuln" in line:
                above = [ln for ln in lines[max(0, i - 8): i] if ln.strip().startswith("#")]
                assert above, f"{p.name}:{i + 1} ignores an advisory without a comment"
