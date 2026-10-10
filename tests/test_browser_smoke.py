"""Click through the evidence home page in a real browser.

The "Delete Client Data" button once did nothing: it sat in a form inside
another form, which browsers drop. Every test that posted to its route
passed. These tests drive the page the way a consultant does.

They need Playwright and Chromium and are skipped without them. CI runs them
in their own job (.github/workflows/tests.yml, browser-smoke).
"""

import json
import threading

import pytest

pw = pytest.importorskip("playwright.sync_api")

import web  # noqa: E402
import web.view  # noqa: E402,F401
import config  # noqa: E402
import consultstore  # noqa: E402
import evidence_collection as ec  # noqa: E402

NAME = "Example Client"
NOTE = "BROWSER-SMOKE-NOTE-7731"


@pytest.fixture
def app_url(tmp_path, monkeypatch):
    # Client data goes to a temporary folder: the delete test must never
    # touch a developer's real data.
    for attr in ("DUMP_DIR", "SCREENSHOT_DIR", "REPORT_DIR"):
        d = tmp_path / attr
        d.mkdir()
        monkeypatch.setattr(config, attr, d)
        monkeypatch.setattr(ec, attr, d)
    monkeypatch.setattr(ec, "TMP_CONSULT_DATA_DIR", str(tmp_path / "legacy"))
    monkeypatch.chdir(config.THIS_DIR)
    # The full report is written to reports/ under the working directory and
    # sent from there; send it from the temporary folder instead.
    real_create = ec.create_printout
    out = tmp_path / "REPORT_DIR" / "report.pdf"
    monkeypatch.setattr("web.view.evidence.create_printout", lambda ctx: real_create(ctx, out_file=str(out)))
    monkeypatch.setattr("web.view.evidence.send_from_directory", lambda _d, _f: web.view.evidence.send_file(str(out)))

    from phone_scanner import db as phone_db
    from werkzeug.serving import make_server

    phone_db.init_db(web.app, None)
    # The real app checks CSRF tokens, so the clicks here must pass that check.
    web.app.config["WTF_CSRF_ENABLED"] = True
    consultstore.save("notes", json.dumps({"consultant_notes": NOTE, "client_notes": "", "client_name": ""}))
    server = make_server("127.0.0.1", 0, web.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def page():
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # no browser installed
            pytest.skip(f"Chromium is not available: {type(e).__name__}")
        context = browser.new_context(accept_downloads=True)
        yield context.new_page()
        browser.close()


def _stored():
    return consultstore.count()


def test_the_report_downloads(app_url, page):
    page.goto(app_url + "/evidence/home")
    page.fill("input[name=client_name]", NAME)
    with page.expect_download(timeout=90000) as dl:
        page.locator("input[name=generate_printout]").click()
    assert open(dl.value.path(), "rb").read(4) == b"%PDF"


def test_the_take_home_copy_downloads(app_url, page):
    page.goto(app_url + "/evidence/home")
    with page.expect_download(timeout=90000) as dl:
        page.locator("button", has_text="Create take-home copy").click()
    assert dl.value.suggested_filename.startswith("notes-")
    assert open(dl.value.path(), "rb").read(4) == b"%PDF"


def test_delete_client_data_asks_first_and_deletes(app_url, page):
    assert _stored() >= 1
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    page.goto(app_url + "/evidence/home")
    page.locator("button", has_text="Delete Client Data").click()
    page.wait_for_load_state()
    assert dialogs and "delete all client data" in dialogs[0]
    assert "Client data deleted" in page.content()
    assert _stored() == 0
    assert NOTE not in page.content()


def test_cancelling_the_confirmation_keeps_the_data(app_url, page):
    page.on("dialog", lambda d: d.dismiss())
    page.goto(app_url + "/evidence/home")
    page.locator("button", has_text="Delete Client Data").click()
    page.wait_for_timeout(500)
    assert _stored() >= 1


def test_every_button_on_the_home_page_belongs_to_a_form_that_reaches_a_route(app_url, page):
    page.goto(app_url + "/evidence/home")
    targets = page.eval_on_selector_all(
        "button[type=submit], input[type=submit]",
        "els => els.map(e => e.getAttribute('formaction') || (e.form && e.form.getAttribute('action')) || '')",
    )
    assert targets, "no submit buttons found"
    for t in targets:
        assert t == "" or t.startswith("/"), t


def test_a_script_post_from_the_page_passes_the_csrf_check(app_url, page):
    # Whichever jQuery the page ends up with must send the token.
    page.goto(app_url + "/evidence/home")
    page.wait_for_load_state("load")
    text = page.evaluate(
        """() => new Promise(done => {
            $.post('/delete/app/1', {appid: 'com.x'})
             .always((a, _s, b) => done((b && b.responseText) || (a && a.responseText) || a));
        })"""
    )
    # The route's own answer, so the CSRF check let the request through.
    assert text == "Invalid device serial."
