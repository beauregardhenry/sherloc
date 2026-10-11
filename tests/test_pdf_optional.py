"""Sherloc runs without WeasyPrint's system libraries (Pango).

Development happens on Intel Macs, where Homebrew often cannot build Pango.
There the app and the tests that do not make a PDF must still work; asking
for a report says what is missing. CI sets SHERLOC_REQUIRE_PDF=1 so a broken
Pango install fails the build instead of skipping the PDF tests.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import evidence_collection as ec
import web
import web.view  # noqa: F401
from phone_scanner import db as phone_db

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def no_weasyprint(monkeypatch):
    """As on a Mac without Pango: importing WeasyPrint fails."""
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    monkeypatch.delitem(sys.modules, "pdfrender", raising=False)


def test_the_app_imports_without_weasyprint():
    code = ("import sys; sys.modules['weasyprint'] = None\n"
            "import web, web.view, evidence_collection, takehome\nprint('ok')")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "sherloc", capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": f"{ROOT / 'sherloc'}:{ROOT / 'sherloc' / 'phone_scanner'}"})
    assert r.stdout.strip() == "ok", r.stderr


def test_making_a_pdf_without_weasyprint_says_what_is_missing(no_weasyprint):
    with pytest.raises(ec.PdfUnavailable, match="Pango"):
        ec.render_printout_pdf({})


@pytest.fixture
def client(monkeypatch):
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    phone_db.init_db(web.app, None)
    monkeypatch.setattr("web.view.evidence.load_report_client", lambda: "Client")
    monkeypatch.setattr("web.view.evidence._printout_context", lambda client: {"url_root": "http://localhost/"})
    return web.app.test_client()


def _flashes(c):
    with c.session_transaction() as s:
        return " ".join(m for _, m in s.get("_flashes", []))


def test_the_report_page_explains_instead_of_crashing(client, no_weasyprint):
    r = client.get("/evidence/printout/")
    assert r.status_code in (302, 303) and r.headers["Location"].endswith("/evidence/home")
    assert "Pango" in _flashes(client)


def test_the_take_home_copy_explains_instead_of_crashing(client, no_weasyprint):
    r = client.post("/evidence/takehome", data={})
    assert r.status_code in (302, 303)
    assert "Pango" in _flashes(client)


def _run_pdf_tests(tmp_path, require):
    # A sitecustomize that blocks WeasyPrint, as on a Mac without Pango.
    (tmp_path / "sitecustomize.py").write_text("import sys\nsys.modules['weasyprint'] = None\n")
    env = {k: v for k, v in os.environ.items() if k != "SHERLOC_REQUIRE_PDF"}
    env["PYTHONPATH"] = str(tmp_path)
    if require:
        env["SHERLOC_REQUIRE_PDF"] = "1"
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           "tests/test_printout.py", "tests/test_takehome.py"],
                          cwd=ROOT, env=env, capture_output=True, text=True)


def test_pdf_tests_skip_without_weasyprint(tmp_path):
    r = _run_pdf_tests(tmp_path, require=False)
    assert r.returncode == 0, r.stdout[-2000:]
    assert "skipped" in r.stdout and "passed" in r.stdout


def test_ci_can_require_the_pdf_tests(tmp_path):
    r = _run_pdf_tests(tmp_path, require=True)
    assert r.returncode != 0
    assert "SHERLOC_REQUIRE_PDF" in r.stdout + r.stderr


def test_ci_requires_the_pdf_tests():
    import yaml

    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "tests.yml").read_text())
    assert workflow["env"]["SHERLOC_REQUIRE_PDF"] == "1"
