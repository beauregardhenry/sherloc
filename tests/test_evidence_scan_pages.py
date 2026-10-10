"""The evidence workflow's scan pages: start a scan, pick apps, investigate
them, or add a device and its apps by hand.

The phone itself is replaced: `get_serial` and `get_scan_data` return a fixed
scan. Everything after that (the forms, what is saved, where each page
leads) runs as in the app.
"""

import pytest

import web
import web.view  # noqa: F401
import config
import evidence_collection as ec
import scanrecord

SER = "ZY22TESTSER"
HSER = config.hmac_serial(SER)
N = ec.ConsultDataTypes


def _app(appid, title, flags):
    return {"appId": appid, "title": title, "app_name": title, "flags": flags, "permissions": []}


@pytest.fixture
def client(monkeypatch):
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    calls = []

    def fake_scan(device, nickname):
        calls.append((device, nickname))
        record = scanrecord.build_scan_record(
            clientid="1", ser=SER, device=device, device_owner=nickname,
            device_name_map={"model": "Pixel 7", "version": "14", "brand": "Google"},
            rooted=False, rooted_reason="No indicators.", include_raw_serial=True,
        )
        return record, [_app("com.spy", "Spy App", ["spyware"])], [_app("com.calc", "Calculator", [])]

    monkeypatch.setattr("web.view.evidence_scan.get_serial", lambda device, nickname: SER)
    monkeypatch.setattr("web.view.evidence_scan.get_scan_data", fake_scan)
    c = web.app.test_client()
    c.scans = calls
    return c


def _scans():
    return ec.load_object_from_json(N.SCANS.value)


def _start(client, **extra):
    data = {"device_type": "android", "device_nickname": "kitchen phone", "submit": "y"}
    data.update(extra)
    return client.post("/evidence/scan", data=data)


# --- starting a scan --------------------------------------------------------------


def test_the_start_page_renders(client):
    assert client.get("/evidence/scan").status_code == 200


def test_a_scan_is_saved_and_leads_to_app_selection(client):
    r = _start(client)
    assert r.status_code in (302, 303)
    assert r.headers["Location"].endswith(f"/evidence/scan/select/{HSER}")
    (scan,) = _scans()
    assert scan.serial == HSER
    assert scan.device_nickname == "kitchen phone"
    apps = {a.appId: a for a in scan.all_apps}
    assert set(apps) == {"com.spy", "com.calc"}
    # Suspicious apps are marked for investigation; the rest are not.
    assert apps["com.spy"].investigate is True
    assert not apps["com.calc"].investigate


def test_scanning_the_same_device_again_offers_a_rescan_instead(client):
    _start(client)
    r = _start(client)
    assert "show-rescan" in r.headers["Location"]
    assert len(client.scans) == 1
    assert len(_scans()) == 1


def test_a_forced_rescan_scans_again_and_replaces_the_old_scan(client):
    _start(client)
    client.post("/evidence/scan/android/kitchen%20phone/force-rescan",
                data={"device_type": "android", "device_nickname": "kitchen phone", "submit": "y"})
    assert len(client.scans) == 2
    assert len(_scans()) == 1


def test_a_scan_error_is_shown_and_returns_to_the_start(client, monkeypatch):
    def broken(device, nickname):
        raise RuntimeError("adb went away")

    monkeypatch.setattr("web.view.evidence_scan.get_scan_data", broken)
    r = _start(client)
    assert "/evidence/scan/android/" in r.headers["Location"]
    assert _scans() == []
    with client.session_transaction() as s:
        assert any("Scan error" in m for _, m in s.get("_flashes", []))


def test_the_manual_button_goes_to_manual_add(client):
    r = _start(client, submit="", manualadd="y")
    assert r.headers["Location"].endswith("/evidence/scan/manualadd/")


# --- choosing apps ------------------------------------------------------------------


def test_the_selection_page_lists_the_apps(client):
    _start(client)
    r = client.get(f"/evidence/scan/select/{HSER}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Spy App" in body and "Calculator" in body


def test_selecting_apps_saves_them_and_leads_to_the_investigation(client):
    _start(client)
    r = client.post(f"/evidence/scan/select/{HSER}", data={
        "apps-0-appId": "com.spy", "apps-0-investigate": "y",
        "apps-1-appId": "com.calc", "apps-1-investigate": "y",
        "submit": "y",
    })
    assert r.headers["Location"].endswith(f"/evidence/scan/investigate/{HSER}")
    (scan,) = _scans()
    assert {a.appId for a in scan.selected_apps} == {"com.spy", "com.calc"}


def test_unselecting_an_app_removes_it(client):
    _start(client)
    client.post(f"/evidence/scan/select/{HSER}", data={
        "apps-0-appId": "com.spy", "apps-0-investigate": "y", "apps-1-appId": "com.calc", "submit": "y"})
    (scan,) = _scans()
    assert [a.appId for a in scan.selected_apps] == ["com.spy"]


def test_a_scan_with_no_apps_still_shows_its_page(client, monkeypatch):
    def no_apps(device, nickname):
        record = scanrecord.build_scan_record(
            clientid="1", ser=SER, device=device, device_owner=nickname,
            device_name_map={}, rooted=False, rooted_reason="", include_raw_serial=True)
        return record, [], []

    monkeypatch.setattr("web.view.evidence_scan.get_scan_data", no_apps)
    _start(client)
    assert client.get(f"/evidence/scan/select/{HSER}").status_code == 200


def test_an_unknown_device_is_not_found(client):
    assert client.get("/evidence/scan/select/HSN_nope").status_code == 404
    assert client.get("/evidence/scan/investigate/HSN_nope").status_code == 404


# --- investigating apps ---------------------------------------------------------------


def _select_both(client):
    _start(client)
    client.post(f"/evidence/scan/select/{HSER}", data={
        "apps-0-appId": "com.spy", "apps-0-investigate": "y",
        "apps-1-appId": "com.calc", "apps-1-investigate": "y", "submit": "y"})


def test_the_investigation_page_renders(client):
    _select_both(client)
    r = client.get(f"/evidence/scan/investigate/{HSER}")
    assert r.status_code == 200
    assert "Spy App" in r.get_data(as_text=True)


def test_investigation_answers_are_saved_per_app(client):
    _select_both(client)
    r = client.post(f"/evidence/scan/investigate/{HSER}", data={
        "selected_apps-0-appId": "com.spy",
        "selected_apps-0-install_info-installed": "no",
        "selected_apps-0-permission_info-access": "yes",
        "selected_apps-0-permission_info-describe": "reads location",
        "selected_apps-0-notes-client_notes": "never installed it",
        "selected_apps-1-appId": "com.calc",
        "selected_apps-1-notes-client_notes": "mine",
        "submit": "y",
    })
    assert r.headers["Location"].endswith("/evidence/home")
    (scan,) = _scans()
    apps = {a.appId: a for a in scan.selected_apps}
    assert apps["com.spy"].notes.client_notes == "never installed it"
    assert apps["com.spy"].permission_info.access == "yes"
    assert apps["com.calc"].notes.client_notes == "mine"


# --- adding a device by hand ------------------------------------------------------------


def _manual(client, apps, serial=""):
    data = {"device_nickname": "old phone", "device_model": "Galaxy S9", "device_serial": serial, "submit": "y"}
    for i, name in enumerate(apps):
        data[f"apps-{i}-app_name"] = name
        data[f"apps-{i}-spyware"] = "y"
    return client.post("/evidence/scan/manualadd/", data=data)


def test_the_manual_page_renders(client):
    assert client.get("/evidence/scan/manualadd/").status_code == 200


def test_a_manual_device_is_saved_with_its_apps(client):
    r = _manual(client, ["Hidden Tracker", "Other Spy"])
    assert r.headers["Location"].endswith("/evidence/scan/investigate/MANADD-old-phone")
    (scan,) = _scans()
    assert scan.manual is True
    assert [a.title for a in scan.selected_apps] == ["Hidden Tracker", "Other Spy"]
    assert all("spyware" in a.flags for a in scan.selected_apps)


def test_manual_apps_keep_their_own_investigation_answers(client):
    # Manual apps have no app id. They used to be matched by app id, so every
    # manual app took the answers given for the last one.
    _manual(client, ["Hidden Tracker", "Other Spy"])
    client.post("/evidence/scan/investigate/MANADD-old-phone", data={
        "selected_apps-0-title": "Hidden Tracker",
        "selected_apps-0-notes-client_notes": "first app",
        "selected_apps-1-title": "Other Spy",
        "selected_apps-1-notes-client_notes": "second app",
        "submit": "y",
    })
    (scan,) = _scans()
    notes = [a.notes.client_notes for a in scan.selected_apps]
    assert notes == ["first app", "second app"]
