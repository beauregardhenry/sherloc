"""The intake form (/form/), stored through SQLAlchemy in `clients_notes`.

Flask-SQLAlchemy creates its engine when the app is set up, from the database
path in config at that moment. Tests therefore swap the engine for one on the
temporary database (conftest.isolated_database); the first test checks that.
"""

import json
import sqlite3

import config
import pytest
import web
import web.view
from phone_scanner import db as phone_db
from web.forms import ClientForm


@pytest.fixture
def client():
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    phone_db.init_db(web.app, None)
    c = web.app.test_client()
    with c.session_transaction() as s:
        s["clientid"] = "20261010_007"
    return c


def _valid_form_data():
    """A value for every field, the first real choice where there are choices."""
    with web.app.test_request_context():
        form = ClientForm()
        data = {}
        for field in form:
            choices = [c[0] for c in (getattr(field, "choices", None) or []) if c[0] not in ("", None)]
            if field.type == "SelectMultipleField":
                data[field.name] = [choices[0]]
            elif choices:
                data[field.name] = choices[0]
            elif field.type == "IntegerField":
                data[field.name] = "1"
            else:
                data[field.name] = "x"
        data["referring_professional_email"] = "caseworker@example.org"
        data["consultant_initials"] = "AB"
        data["general_notes"] = "INTAKE-MARKER-4410"
        return data


def _rows():
    con = sqlite3.connect(config.SQL_DB_PATH.replace("sqlite:///", ""))
    try:
        return con.execute("select clientid, consultant_initials, general_notes, chief_concerns from clients_notes").fetchall()
    finally:
        con.close()


def test_the_orm_writes_to_the_test_database(client):
    with web.app.app_context():
        url = str(web.sa.engine.url)
    assert url.replace("sqlite:///", "") == config.SQL_DB_PATH.replace("sqlite:///", "")


def test_without_a_client_session_it_goes_home():
    web.app.config.update(TESTING=True)
    assert web.app.test_client().get("/form/").status_code in (302, 303)


def test_the_form_renders(client):
    assert client.get("/form/").status_code == 200


def test_a_valid_form_is_saved_for_this_client(client):
    r = client.post("/form/", data=_valid_form_data())
    assert r.status_code == 200
    ((clientid, initials, notes, concerns),) = _rows()
    assert (clientid, initials, notes) == ("20261010_007", "AB", "INTAKE-MARKER-4410")
    assert json.loads(concerns) == ["spyware"]


def test_an_incomplete_form_is_not_saved(client):
    data = _valid_form_data()
    data.pop("consultant_initials")
    client.post("/form/", data=data)
    assert _rows() == []


def test_a_second_visit_goes_to_editing(client):
    client.post("/form/", data=_valid_form_data())
    r = client.get("/form/")
    assert r.headers["Location"].endswith("/form/edit/")


def test_an_edit_updates_the_saved_form(client):
    client.post("/form/", data=_valid_form_data())
    r = client.post("/form/edit/", data={"clientnote": "1"})
    assert r.status_code == 200
    data = _valid_form_data()
    data["general_notes"] = "EDITED-NOTE"
    client.post("/form/edit/", data=data)
    ((clientid, _, notes, _),) = _rows()
    assert (clientid, notes) == ("20261010_007", "EDITED-NOTE")


@pytest.mark.parametrize("required", ["consultant_initials", "fjc", "referring_professional", "chief_concerns", "vulnerabilities"])
def test_questions_marked_required_are_enforced(client, required):
    """Labels ending in * are required. The column defaults used to make
    wtforms_alchemy add Optional(), which skipped InputRequired on blanks."""
    data = _valid_form_data()
    data.pop(required)
    r = client.post("/form/", data=data)
    assert r.status_code == 200
    assert _rows() == []


def test_the_optional_email_can_be_left_blank(client):
    data = _valid_form_data()
    data["referring_professional_email"] = ""
    client.post("/form/", data=data)
    assert len(_rows()) == 1


def test_an_invalid_edit_keeps_the_saved_form(client):
    client.post("/form/", data=_valid_form_data())
    client.post("/form/edit/", data={"clientnote": "1"})
    data = _valid_form_data()
    data["general_notes"] = "SHOULD-NOT-SAVE"
    data.pop("consultant_initials")
    r = client.post("/form/edit/", data=data)
    assert r.status_code == 200
    ((_, initials, notes, concerns),) = _rows()
    assert (initials, notes, concerns) == ("AB", "INTAKE-MARKER-4410", '["spyware"]')


def test_a_form_saved_without_checkboxes_opens_for_editing(client):
    """Older rows can hold '' in the checkbox columns; json.loads('') crashed."""
    client.post("/form/", data=_valid_form_data())
    con = sqlite3.connect(config.SQL_DB_PATH.replace("sqlite:///", ""))
    con.execute("update clients_notes set checkups = ''")
    con.commit()
    con.close()
    assert client.post("/form/edit/", data={"clientnote": "1"}).status_code == 200


def test_editing_without_choosing_a_form_goes_back_to_the_list(client):
    r = client.post("/form/edit/", data=_valid_form_data())
    assert r.status_code in (302, 303)
