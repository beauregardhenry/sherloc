"""The PDF printout is rendered from user-entered text by WeasyPrint.

Notes, nicknames and app names are free text, so that text is escaped before
it is turned into HTML, and the renderer may only load the app's own static
files (logos, screenshots), never other local files or the network.
"""

import re
import shutil
import subprocess

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import evidence_collection as ec
import pdfrender

SECTIONS = ("devices", "accounts", "sharing", "smarthome", "kids")

PAYLOADS = [
    '<iframe src="file:///etc/passwd"></iframe>',
    "<img src=x onerror=alert(1)>",
    "<script>document.write('x')</script>",
]


def _context(**overrides):
    ctx = {
        "url_root": "http://localhost:6200/",
        "sherloc_version": "test",
        "setup": {"client": "Client", "date": "2026-01-01"},
        "notes": {"consultant_notes": "", "client_notes": ""},
        "scans": [],
        "accounts": [],
        "taq": {
            "all_risks": [],
            **{k: {"risk_report": {"risk_details": []}} for k in SECTIONS},
        },
        "formquestions": {"taq": {"devices": {}, "accounts": {}, "sharing": {}, "smarthome": {}, "kids": {}}},
        "select_text": {},
        "risks": [],
    }
    ctx.update(overrides)
    return ctx


@pytest.mark.parametrize("payload", PAYLOADS)
def test_notes_are_escaped_in_the_printout_html(payload):
    ctx = _context(notes={"consultant_notes": payload, "client_notes": payload})
    html = ec.render_printout_html(ctx)
    assert payload not in html
    assert "<iframe" not in html
    assert "<script>" not in html
    assert "<img src=x" not in html


def test_client_name_is_escaped_in_the_printout_html():
    payload = PAYLOADS[0]
    ctx = _context(setup={"client": payload, "date": "now"})
    assert payload not in ec.render_printout_html(ctx)


def test_ordinary_text_is_kept():
    ctx = _context(notes={"consultant_notes": "Tom & Jerry's phone", "client_notes": ""})
    html = ec.render_printout_html(ctx)
    assert "Tom &amp; Jerry&#39;s phone" in html


needs_pdftotext = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext not installed")


def _text(data: bytes) -> str:
    return subprocess.run(["pdftotext", "-", "-"], input=data, capture_output=True).stdout.decode()


@needs_pdftotext
def test_a_hostile_note_does_not_pull_a_local_file_into_the_pdf(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET-MARKER-12345")
    ctx = _context(
        notes={
            "consultant_notes": f'<iframe src="file://{secret}" width="500" height="200"></iframe>',
            "client_notes": "",
        }
    )
    out = ec.create_printout(ctx, out_file=str(tmp_path / "out.pdf"))
    data = open(out, "rb").read()
    assert data[:4] == b"%PDF"
    assert "TOP-SECRET-MARKER-12345" not in _text(data)


# --- the renderer itself, given raw HTML (as if escaping had failed) ---------


@needs_pdftotext
def test_the_renderer_does_not_load_local_stylesheets(tmp_path):
    css = tmp_path / "evil.css"
    css.write_text('body::before { content: "LOCAL-CSS-LOADED-551"; }')
    html = f'<html><head><link rel="stylesheet" href="file://{css}"></head><body><p>plain</p></body></html>'
    text = _text(pdfrender.render_pdf(html, url_root="http://localhost:6200/", footer=""))
    assert "plain" in text
    assert "LOCAL-CSS-LOADED-551" not in text


def test_the_fetcher_only_serves_files_under_webstatic():
    f = pdfrender.StaticOnlyFetcher("http://localhost:6200/")
    assert f.fetch("http://localhost:6200/webstatic/images/mtc-logo.png").status == 200
    for url in (
        "file:///etc/passwd",
        "http://localhost:6200/webstatic/../config.py",
        "http://localhost:6200/webstatic/%2e%2e/config.py",
        "http://localhost:6200/static_data/pii.key",
        "http://evil.example/x.png",
        "https://localhost:6200/webstatic/style.css",
        "data:text/css,body{}",
    ):
        with pytest.raises(ValueError):
            f.fetch(url)


@needs_pdftotext
def test_script_in_the_page_does_not_run():
    html = "<html><body><p>plain</p><script>document.write('SCRIPT-RAN-77')</script></body></html>"
    text = _text(pdfrender.render_pdf(html, url_root="http://localhost:6200/", footer=""))
    assert "plain" in text
    assert "SCRIPT-RAN-77" not in text


@needs_pdftotext
def test_the_full_report_has_the_clinic_footer_with_page_numbers(tmp_path):
    out = ec.create_printout(_context(), out_file=str(tmp_path / "out.pdf"))
    text = _text(open(out, "rb").read())
    assert "Created by Madison Tech Clinic using Sherloc" in text
    assert re.search(r"Page 1 of \d+", text)


def test_the_logo_is_embedded_from_the_static_folder(tmp_path):
    out = ec.create_printout(_context(), out_file=str(tmp_path / "out.pdf"))
    assert b"/Subtype /Image" in open(out, "rb").read() or b"/Subtype/Image" in open(out, "rb").read()


def test_no_pdfkit_or_wkhtmltopdf_is_used():
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    assert "pdfkit" not in (root / "sherloc" / "requirements.txt").read_text()
    code = "\n".join(p.read_text() for p in (root / "sherloc").rglob("*.py"))
    assert "import pdfkit" not in code
    assert "PYSEC-2026-2860" not in (root / ".github" / "workflows" / "audit.yml").read_text()


def _png():
    # A 1x1 PNG.
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )


def test_screenshots_outside_webstatic_are_served(tmp_path, monkeypatch):
    # Screenshots live under SHERLOC_DATA_DIR (#55) and are linked as
    # client-screenshots/...; the PDF must still include them.
    import config

    shots = tmp_path / "shots"
    (shots / "HSN_x" / "rooting").mkdir(parents=True)
    (shots / "HSN_x" / "rooting" / "1.png").write_bytes(_png())
    monkeypatch.setattr(config, "SCREENSHOT_DIR", shots)
    f = pdfrender.StaticOnlyFetcher("http://localhost:6200/")
    assert f.fetch("http://localhost:6200/client-screenshots/HSN_x/rooting/1.png").status == 200
    (tmp_path / "secret.txt").write_text("no")
    for url in ("http://localhost:6200/client-screenshots/../secret.txt",
                "http://localhost:6200/client-screenshots/%2e%2e/secret.txt",
                "http://localhost:6200/client-screenshots/HSN_x/missing.png"):
        with pytest.raises(ValueError):
            f.fetch(url)


def test_a_screenshot_is_embedded_in_the_report(tmp_path, monkeypatch):
    import config

    shots = tmp_path / "shots"
    (shots / "HSN_x" / "rooting").mkdir(parents=True)
    shot = shots / "HSN_x" / "rooting" / "1.png"
    shot.write_bytes(_png())
    monkeypatch.setattr(config, "SCREENSHOT_DIR", shots)
    html = f'<html><body><img src="http://localhost:6200/{config.screenshot_path(str(shot))}"/></body></html>'
    pdf = pdfrender.render_pdf(html, url_root="http://localhost:6200/", footer="")
    assert b"/Subtype /Image" in pdf or b"/Subtype/Image" in pdf
