"""CSRF tokens on every state-changing request.

web/security.py already rejects cross-site requests by their Sec-Fetch-Site
and Origin headers. A browser that sends neither (older Safari, for one) gets
through that guard, so every POST also needs the session's CSRF token.
"""

import re
from pathlib import Path

import pytest

import web
import web.view  # noqa: F401
import config
from phone_scanner import db as phone_db

TEMPLATES = Path(__file__).resolve().parent.parent / "sherloc" / "templates"

# A value for each URL variable, so every POST route can be called.
ARGS = {"id": "1", "ser": "HSN_x", "scanid": "1", "device_type": "android",
        "device_nickname": "phone", "show_rescan": "True"}


def _post_rules():
    for rule in web.app.url_map.iter_rules():
        if "POST" in rule.methods:
            yield rule.rule, rule.endpoint


def _url(rule):
    return re.sub(r"<(?:[^:>]+:)?([^>]+)>", lambda m: ARGS[m.group(1)], rule)


@pytest.fixture
def csrf_on():
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    phone_db.init_db(web.app, None)
    return web.app.test_client()


def _token(client, path="/evidence/home"):
    page = client.get(path).get_data(as_text=True)
    m = re.search(r'name="csrf-token" content="([^"]+)"', page)
    assert m, "every page carries the token in a <meta name=csrf-token>"
    return m.group(1)


@pytest.fixture
def no_shutdown(monkeypatch):
    """Record calls that stop the app or delete client data instead of making them."""
    import web.view.control as control

    calls = []
    monkeypatch.setattr(control, "stop_server", lambda: calls.append(1))
    # Without protection, /evidence/delete-data would empty the real folders.
    monkeypatch.setattr("web.view.evidence.delete_client_data", lambda: calls.append(2))
    return calls


@pytest.mark.parametrize("rule,endpoint", sorted(_post_rules()))
def test_a_post_without_a_token_is_refused(csrf_on, no_shutdown, rule, endpoint):
    r = csrf_on.post(_url(rule), data={})
    assert r.status_code == 400, endpoint
    assert "Please reload the page" in r.get_data(as_text=True)
    assert no_shutdown == []


def test_screenshots_survive_a_forged_delete(csrf_on, tmp_path, monkeypatch):
    shots = tmp_path / "shots"
    (shots / "HSN_x" / "rooting").mkdir(parents=True)
    shot = shots / "HSN_x" / "rooting" / "1.png"
    shot.write_bytes(b"png")
    monkeypatch.setattr(config, "SCREENSHOT_DIR", shots)
    csrf_on.post("/evidence/screenshots", data={
        "root_screenshots-0-fname": str(shot), "root_screenshots-0-delete": "y"})
    assert shot.exists()


def test_a_post_with_the_token_goes_through(csrf_on):
    token = _token(csrf_on)
    r = csrf_on.post("/evidence/home", data={"csrf_token": token, "client_name": "x"})
    assert "Please reload the page" not in r.get_data(as_text=True)


def test_scripts_can_send_the_token_as_a_header(csrf_on):
    token = _token(csrf_on)
    r = csrf_on.post("/delete/app/1", data={"appid": "com.x"}, headers={"X-CSRFToken": token})
    # The route answers for itself (here: no serial), not the CSRF check.
    assert r.get_data(as_text=True) == "Invalid device serial."


def test_the_token_does_not_expire_during_a_consultation():
    # Flask-WTF's default is one hour. A form left open longer would lose
    # its answers on submit.
    assert web.app.config["WTF_CSRF_TIME_LIMIT"] is None


def test_jquery_posts_carry_the_token():
    main = (TEMPLATES / "main.html").read_text()
    assert 'name="csrf-token" content="{{ csrf_token() }}"' in main
    js = (TEMPLATES.parent / "webstatic" / "myjscript.js").read_text()
    assert 'ajaxSetup({headers: {"X-CSRFToken"' in js
    assert 'addEventListener("DOMContentLoaded", sherlocCsrfSetup)' in js


def _post_forms(html):
    for m in re.finditer(r"<form\b[^>]*>(.*?)</form>", html, re.S | re.I):
        if re.search(r"method\s*=\s*['\"]?post", m.group(0)[:200], re.I):
            yield m.group(0)


@pytest.mark.parametrize("template", sorted(p.name for p in TEMPLATES.glob("*.html")))
def test_every_post_form_includes_the_token(template):
    html = (TEMPLATES / template).read_text()
    missing = [f[:80] for f in _post_forms(html) if not re.search(r"csrf_token|hidden_tag", f)]
    assert missing == []
