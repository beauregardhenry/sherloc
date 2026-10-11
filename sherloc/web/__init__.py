from datetime import datetime, timedelta
from time import strftime
import logging
import os
import config
from flask import Flask, g, session, request
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from htmlclean import clean_description
from web.security import register_request_guards

config.ensure_dirs()

app = Flask(__name__, static_folder="../webstatic", template_folder="../templates/")
app.config["SQLALCHEMY_DATABASE_URI"] = config.SQL_DB_PATH
# Echoed statements include client notes and device serials.
app.config["SQLALCHEMY_ECHO"] = bool(int(os.getenv("SHERLOC_SQL_ECHO", "0")))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Signs the session cookie and the CSRF tokens.
app.config["SECRET_KEY"] = config.FLASK_SECRET
sa = SQLAlchemy(app)
# The evidence pages use Flask-Bootstrap's base template. Serve its jQuery and
# Bootstrap from the package instead of a CDN, so the pages work offline and no
# outside server sees when a consultation is running.
app.config["BOOTSTRAP_SERVE_LOCAL"] = True
Bootstrap(app)

register_request_guards(app)
app.jinja_env.filters["clean_html"] = clean_description

logger = logging.getLogger(__name__)

import web.view  # noqa: F401 - registers the routes

import clientdata
import indicators


@app.context_processor
def inject_client_data():
    return {"client_data": clientdata.summary()}


@app.context_processor
def inject_indicator_list():
    return {"indicator_list": indicators.describe(indicators.summary())}


@app.before_request
def make_session_permanent():
    # Cookies from earlier versions carried the client's name; drop it.
    session.pop("client", None)
    session.permanent = True
    # expires at midnight of new day
    app.permanent_session_lifetime = (datetime.now() + timedelta(days=1)).replace(
        hour=0, minute=0, second=0
    ) - datetime.now()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


@app.after_request
def do_not_store(response):
    """Pages, screenshots and reports hold client data: keep them out of the
    browser's disk cache."""
    response.headers["Cache-Control"] = "no-store"
    return response


@app.after_request
def after_request(response):
    """Logging after every request."""
    # Flask already logs an unhandled exception (a 500) with its traceback.
    if response.status_code != 500:
        ts = strftime("[%Y-%b-%d %H:%M]")
        logger.error(
            "%s %s %s %s %s %s",
            ts,
            request.remote_addr,
            request.method,
            request.scheme,
            # The route pattern, not the URL: paths and query strings carry
            # device serials and app ids.
            request.url_rule.rule if request.url_rule else "-",
            response.status,
        )
    return response
