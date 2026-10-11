"""The intake-form summary script (phone_scanner/isdi_summarize.py)."""

import json
import sqlite3

import config
import intake_choices
import web
import web.view  # noqa: F401
from phone_scanner import db as phone_db
from phone_scanner import isdi_summarize
from web.forms import ClientForm


def _db_with_forms(rows):
    web.app.config.update(TESTING=True)
    phone_db.init_db(web.app, None)
    path = config.SQL_DB_PATH.replace("sqlite:///", "")
    con = sqlite3.connect(path)
    for concerns, vulns in rows:
        con.execute("insert into clients_notes (clientid, chief_concerns, vulnerabilities) values ('c', ?, ?)",
                    (concerns, vulns))
    con.execute("insert into scan_res (clientid, serial, device) values ('c', 'HSN_a', 'android')")
    con.commit()
    con.close()
    return path


def test_the_form_and_the_summary_share_one_list_of_choices():
    # The summary used to keep its own copy of the labels.
    with web.app.test_request_context():
        form = ClientForm()
        assert form.chief_concerns.choices == intake_choices.CHIEF_CONCERNS
        assert form.vulnerabilities.choices == intake_choices.VULNERABILITIES
        assert form.checkups.choices == intake_choices.CHECKUPS


def test_checkbox_answers_are_counted_with_their_labels():
    path = _db_with_forms([(json.dumps(["spyware", "sms"]), json.dumps(["none"])),
                           (json.dumps(["spyware"]), json.dumps(["none"]))])
    summ = isdi_summarize.ISDiSummary(path)
    hist, overlap = summ.hist_checkbox("chief_concerns", dict(intake_choices.CHIEF_CONCERNS))
    assert hist == {"Worried about spyware/tracking": 2, "SMS texts": 1}
    assert overlap == {2: 1, 1: 1}


def test_a_form_with_no_boxes_ticked_is_counted_not_a_crash():
    path = _db_with_forms([("", json.dumps(["none"]))])
    hist, overlap = isdi_summarize.ISDiSummary(path).hist_checkbox("chief_concerns")
    assert hist == {} and overlap == {0: 1}


def test_the_summary_shows_the_device_count_as_a_number():
    path = _db_with_forms([(json.dumps(["spyware"]), json.dumps(["none"]))])
    text = str(isdi_summarize.ISDiSummary(path))
    assert "Number of devices scanned (iOS or Android): 1" in text
    assert "bound method" not in text


def test_two_summaries_do_not_share_their_counts():
    path = _db_with_forms([(json.dumps(["spyware"]), json.dumps(["none"]))])
    a = isdi_summarize.ISDiSummary(path)
    a.hist_checkbox("chief_concerns")
    assert isdi_summarize.ISDiSummary(path).checkbox_hists == {}
