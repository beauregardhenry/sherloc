"""A copy of the report the client can take home.

The full report is for the clinic's records. It names the clinic, prints
contact details, device serial numbers and the consultant's own comments. A
client who takes a copy home may share a phone, a printer or a bag with the
person who is harming them, so the take-home copy leaves those out and can be
protected with a password.
"""

import io
import re
import shutil
import subprocess

import pypdf
import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
import evidence_collection as ec
import takehome
from tests.test_printout import _context

SERIAL = "SERIAL-ZY224F8TKG"
CONSULTANT = "consultant-only-remark-4471"
CLIENT = "client-remark-5582"
NAME = "Jane Roe"


def _full_context(**extra):
    notes = {"consultant_notes": CONSULTANT, "client_notes": CLIENT}
    scan = {
        "device_manufacturer": "Acme",
        "device_model": "Phone9",
        "device_version": "14",
        "device_nickname": "kitchen",
        "serial_or_udid": SERIAL,
        "device_type": "android",
        "risk_report": {"risk_present": False, "risk_details": []},
        "screenshot_files": [],
        "apps": [],
        "notes": notes,
    }
    ctx = _context(
        setup={"client": NAME, "date": "2026-10-09"},
        notes=notes,
        scans=[scan],
    )
    ctx.update(extra)
    return ctx


# --- content ---------------------------------------------------------------


def test_the_full_report_is_unchanged():
    html = ec.render_printout_html(_full_context())
    for text in ("Madison Tech Clinic", "techclinic.madison@gmail.com", NAME, SERIAL, CONSULTANT, CLIENT):
        assert text in html


@pytest.mark.parametrize(
    "text",
    ["Madison", "techclinic", "UW-Madison", "mtc-logo", "Tech Clinic", NAME, SERIAL, CONSULTANT],
)
def test_the_take_home_copy_leaves_out_what_identifies_the_clinic_and_the_client(text):
    html = ec.render_printout_html(_full_context(takehome=True))
    assert text not in html


def test_the_take_home_copy_keeps_the_findings_and_the_clients_own_comments():
    html = ec.render_printout_html(_full_context(takehome=True))
    assert CLIENT in html
    assert "Phone9" in html
    assert "2026-10-09" in html


def test_the_take_home_copy_has_no_screenshot_metadata():
    html = ec.render_printout_html(_full_context(takehome=True))
    assert "Screenshot Metadata" not in html


def test_take_home_text_is_still_escaped():
    payload = '<iframe src="file:///etc/passwd"></iframe>'
    ctx = _full_context(takehome=True, notes={"consultant_notes": "", "client_notes": payload})
    assert "<iframe" not in ec.render_printout_html(ctx)


# --- pdf options -----------------------------------------------------------


def test_take_home_footer_does_not_name_the_clinic():
    opts = ec.printout_pdf_options(takehome=True)
    assert "Madison" not in opts["footer-center"]
    assert "Sherloc" not in opts["footer-center"]
    assert "[page]" in opts["footer-center"]


def test_take_home_options_keep_the_security_settings():
    opts = ec.printout_pdf_options(takehome=True)
    assert "disable-javascript" in opts
    assert not opts.get("enable-local-file-access")


def test_the_full_report_footer_is_unchanged():
    assert "Madison Tech Clinic" in ec.printout_pdf_options()["footer-center"]


# --- file name --------------------------------------------------------------


def test_file_name_is_neutral_and_different_each_time():
    a, b = takehome.neutral_filename(), takehome.neutral_filename()
    assert a != b
    assert re.fullmatch(r"notes-[0-9a-f]{12}\.pdf", a)


# --- password ---------------------------------------------------------------


def _pdf_bytes(text="hello"):
    w = pypdf.PdfWriter()
    w.add_blank_page(200, 200)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def test_a_password_encrypts_the_pdf():
    data = takehome.protect_pdf(_pdf_bytes(), "correct horse")
    r = pypdf.PdfReader(io.BytesIO(data))
    assert r.is_encrypted
    assert r.decrypt("wrong") == 0
    assert r.decrypt("correct horse") != 0
    assert len(r.pages) == 1


def test_a_password_uses_aes_256():
    data = takehome.protect_pdf(_pdf_bytes(), "pw")
    assert b"/AESV3" in data


def test_without_a_password_the_pdf_is_not_encrypted():
    data = takehome.protect_pdf(_pdf_bytes(), "")
    assert not pypdf.PdfReader(io.BytesIO(data)).is_encrypted
    assert not pypdf.PdfReader(io.BytesIO(takehome.protect_pdf(_pdf_bytes(), None))).is_encrypted


def _tool_pdf():
    w = pypdf.PdfWriter()
    w.add_blank_page(200, 200)
    w.metadata = {
        "/Creator": "wkhtmltopdf 0.12.6",
        "/Producer": "Qt 5.15.13",
        "/CreationDate": "D:20261009185502-05'00'",
        "/Author": "Madison Tech Clinic",
    }
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


@pytest.mark.parametrize("password", ["", "pw"])
def test_the_file_does_not_name_the_tool_or_the_time_it_was_made(password):
    data = takehome.protect_pdf(_tool_pdf(), password)
    reader = pypdf.PdfReader(io.BytesIO(data))
    if password:
        reader.decrypt(password)
    meta = dict(reader.metadata or {})
    assert meta.get("/Title") == "Notes"
    assert set(meta) == {"/Title"}
    assert b"wkhtmltopdf" not in data and b"Madison" not in data


# --- the route --------------------------------------------------------------

needs_tools = pytest.mark.skipif(
    shutil.which("wkhtmltopdf") is None or shutil.which("pdftotext") is None,
    reason="wkhtmltopdf or pdftotext not installed",
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    monkeypatch.chdir(config.THIS_DIR)
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "reports")
    (tmp_path / "reports").mkdir()
    monkeypatch.setattr("web.view.evidence.load_json_data", lambda t: {} if t in (1, 4) else [])
    monkeypatch.setattr("web.view.evidence.REPORT_DIR", tmp_path / "reports", raising=False)
    c = web.app.test_client()
    return c


@needs_tools
def test_take_home_route_returns_a_pdf_without_the_client_name(client, tmp_path):
    r = client.post("/evidence/takehome", data={"takehome_password": ""})
    assert r.status_code == 200
    assert r.data[:4] == b"%PDF"
    disposition = r.headers.get("Content-Disposition", "")
    assert "Roe" not in disposition
    text = subprocess.run(["pdftotext", "-", "-"], input=r.data, capture_output=True).stdout.decode()
    assert "Madison" not in text


@needs_tools
def test_take_home_route_with_password_returns_an_encrypted_pdf(client):
    r = client.post("/evidence/takehome", data={"takehome_password": "s3cret-pw"})
    assert r.status_code == 200
    reader = pypdf.PdfReader(io.BytesIO(r.data))
    assert reader.is_encrypted
    assert reader.decrypt("s3cret-pw") != 0


@needs_tools
def test_the_password_is_not_kept(client):
    client.post("/evidence/takehome", data={"takehome_password": "s3cret-pw"})
    with client.session_transaction() as s:
        assert "s3cret-pw" not in repr(dict(s))


@needs_tools
def test_no_unprotected_copy_is_left_on_disk_when_a_password_is_set(client, tmp_path):
    client.post("/evidence/takehome", data={"takehome_password": "s3cret-pw"})
    for f in list((tmp_path / "reports").rglob("*")) + list(config.THIS_DIR.glob("reports/*.pdf")):
        if f.is_file() and f.suffix == ".pdf":
            assert pypdf.PdfReader(str(f)).is_encrypted, f


def test_take_home_route_rejects_get(client):
    assert client.get("/evidence/takehome").status_code == 405


def test_the_home_page_offers_the_take_home_copy(client):
    # The button posts to its own route; a form inside the main form would be dropped.
    from pathlib import Path

    text = (Path(config.THIS_DIR) / "templates" / "evidence-home.html").read_text()
    assert "evidence_takehome" in text
    assert 'name="takehome_password"' in text
    assert 'type="password"' in text
