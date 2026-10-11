"""Pages load their scripts and stylesheets from Sherloc itself.

Clinics may run Sherloc without an internet connection, and a page that pulls
code from a CDN also tells that CDN when a consultation is happening.
"""

import re

import pytest

import web
import web.view  # noqa: F401
from phone_scanner import db as phone_db

PAGES = ["/evidence/home", "/evidence/taq", "/evidence/account/1", "/evidence/scan",
         "/evidence/scan/manualadd/", "/evidence/screenshots", "/form/", "/instruction",
         "/scan", "/privacy"]
EXTERNAL = re.compile(r"""<(?:script|link)\b[^>]*\b(?:src|href)=["']((?:https?:)?//[^"']+)""", re.I)


@pytest.fixture
def client():
    web.app.config.update(TESTING=True)
    phone_db.init_db(web.app, None)
    c = web.app.test_client()
    with c.session_transaction() as s:
        s["clientid"] = "20261010_001"
    return c


@pytest.mark.parametrize("path", PAGES)
def test_no_page_loads_code_from_another_host(client, path):
    html = client.get(path).get_data(as_text=True)
    assert EXTERNAL.findall(html) == []


def test_the_local_copies_are_served(client):
    html = client.get("/evidence/home").get_data(as_text=True)
    local = re.findall(r"""<(?:script|link)\b[^>]*\b(?:src|href)=["'](/webstatic/[^"'?]+)""", html)
    assert local
    for url in local:
        assert client.get(url).status_code == 200, url
