from flask import redirect, request, session, url_for
from phone_scanner import AndroidScan, IosScan, TestScan
from phone_scanner.db import new_client_id
from web import app


# all in all, this particular section has a terrible code smell...
def get_device(k):
    if k == "android":
        return AndroidScan()
    if k == "ios":
        return IosScan()
    if k == "test":
        return TestScan()

def current_client_id():
    """The client ID of this consultation, created on first use.

    The session ends at midnight (see web/__init__.py), and "Delete client
    data" clears it, so the next client gets a new ID.
    """
    if "clientid" not in session:
        session["clientid"] = new_client_id()
    return session["clientid"]


@app.route("/", methods=["GET"])
def index():
    if request.args.get("newid") is not None:
        session.pop("clientid", None)
    current_client_id()

    return redirect(url_for('evidence_home'))
