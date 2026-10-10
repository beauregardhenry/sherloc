"""Client data must not end up in the browser's own storage on disk.

Flask's session cookie is signed, not encrypted: anyone with the browser
profile can read it, and Sherloc made it last a day. The client's name was
kept there for the report. Pages were also sent without `Cache-Control:
no-store`, so the browser could keep copies of them in its cache.
"""

import pytest

import web
import web.view  # noqa: F401

NAME = "Jane Roe-Marker"


@pytest.fixture
def client(monkeypatch):
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    captured = {}
    monkeypatch.setattr("web.view.evidence.create_printout", lambda ctx, *a, **k: (captured.setdefault("client", ctx["setup"]["client"]), "reports/fake.pdf")[1])
    monkeypatch.setattr("web.view.evidence.send_from_directory", lambda *a, **k: "pdf")
    c = web.app.test_client()
    c.captured = captured
    return c


def _session_data(c):
    cookie = c.get_cookie("session")
    if cookie is None:
        return {}
    serializer = web.app.session_interface.get_signing_serializer(web.app)
    return serializer.loads(cookie.value)


def test_the_client_name_is_not_kept_in_the_session_cookie(client):
    client.post("/evidence/home", data={"client_name": NAME, "generate_printout": "y"})
    assert NAME not in repr(_session_data(client))


def test_the_report_still_gets_the_client_name(client):
    client.post("/evidence/home", data={"client_name": NAME, "generate_printout": "y"})
    client.get("/evidence/printout/")
    assert client.captured.get("client") == NAME


def test_the_report_without_a_name_sends_the_consultant_back(client):
    r = client.get("/evidence/printout/")
    assert r.status_code in (302, 303)


def test_deleting_client_data_forgets_the_name(client, monkeypatch, tmp_path):
    import evidence_collection as ec

    for name in ("DUMP_DIR", "SCREENSHOT_DIR", "REPORT_DIR"):
        monkeypatch.setattr(ec, name, tmp_path / name)
    monkeypatch.setattr(ec, "TMP_CONSULT_DATA_DIR", str(tmp_path / "legacy"))
    client.post("/evidence/home", data={"client_name": NAME, "generate_printout": "y"})
    ec.delete_client_data()
    r = client.get("/evidence/printout/")
    assert r.status_code in (302, 303)


@pytest.mark.parametrize("path", ["/evidence/home", "/privacy", "/webstatic/style.css"])
def test_every_response_tells_the_browser_not_to_store_it(client, path):
    r = client.get(path, headers={"Host": "localhost:6200"})
    assert "no-store" in r.headers.get("Cache-Control", "")
