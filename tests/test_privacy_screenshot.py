"""The screenshot route (/privacy/<device>/<cmd>/<context>/<ser>).

It runs commands on the phone and writes a file, so it is a POST: a GET
could be triggered by a link or a prefetch, and CSRF tokens only cover POST.
The image it returns must point to where screenshots now live
(/client-screenshots/..., #55), not to webstatic/.
"""

import re
from pathlib import Path

import pytest

import config
import web
import web.view  # noqa: F401
from phone_scanner import privacy_scan_android as psa

URL = "/privacy/android/screenshot/ctx/ZY224F8TKG"
JS = Path(__file__).resolve().parent.parent / "sherloc" / "webstatic" / "myjscript.js"


@pytest.fixture
def client(monkeypatch):
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    calls = []
    import sys

    # web.view re-exports the view function `privacy`, which hides the module.
    monkeypatch.setattr(sys.modules["web.view.privacy"], "do_privacy_check", lambda ser, cmd, ctx: calls.append((ser, cmd, ctx)) or "ok")
    c = web.app.test_client()
    c.calls = calls
    return c


def test_a_get_does_not_take_a_screenshot(client):
    assert client.get(URL).status_code == 405
    assert client.calls == []


def test_a_post_takes_it(client):
    assert client.post(URL).status_code == 200
    assert client.calls == [("ZY224F8TKG", "screenshot", "ctx")]


def test_the_page_script_posts_with_the_csrf_token():
    js = JS.read_text()
    body = js[js.index("function getScreenshot"):]
    body = body[: body.index("\n}\n")]
    assert re.search(r"method:\s*['\"]POST['\"]", body)
    assert "X-CSRFToken" in body


def test_an_android_screenshot_links_to_the_client_screenshot_folder(fake_adb, tmp_path, monkeypatch):
    shots = tmp_path / "data" / "shots"
    monkeypatch.setattr(config, "SCREENSHOT_DIR", shots)
    fname = config.create_screenshot_fname("ctx", "HSN_x")
    fake_adb.respond([{"match": "exec-out screencap -p", "stdout": "PNGDATA"}])
    with web.app.test_request_context():
        html = psa.take_screenshot("ZY224F8TKG", fname=fname)
    src = re.search(r"src='([^']+)'", html).group(1)
    assert src.startswith("/client-screenshots/HSN_x/ctx/"), src
    assert web.app.test_client().get(src).status_code == 200
