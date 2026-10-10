"""Request guards for a web app that only the local consultant should use.

Two attacks matter even when the server listens on 127.0.0.1:

* A web page the consultant has open can make their browser send requests to
  the app (cross-site request forgery). Several routes change state or run
  device commands on a plain GET.
* DNS rebinding lets a remote site read responses by getting its own hostname
  to resolve to 127.0.0.1. Rejecting unknown Host headers stops that.

Cross-site requests are refused by their Sec-Fetch-Site and Origin headers.
A browser that sends neither gets past that check, so every POST must also
carry the session's CSRF token (Flask-WTF), as a form field or, from
scripts, the X-CSRFToken header.
"""

from urllib.parse import urlsplit

import config
from flask import abort, request
from flask_wtf.csrf import CSRFError, CSRFProtect

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Values a browser sends when the request came from the app itself, or from the
# person typing a URL or using a bookmark.
TRUSTED_FETCH_SITES = {"same-origin", "none"}


def _hostname(value):
    """Return the lowercase host without port or brackets, or None."""
    if not value:
        return None
    try:
        return urlsplit("//" + value).hostname
    except ValueError:
        return None


def _origin_hostname(origin):
    try:
        return urlsplit(origin).hostname
    except ValueError:
        return None


csrf = CSRFProtect()

CSRF_MESSAGE = (
    "<h1>Please reload the page</h1>"
    "<p>This request was refused because it did not come from a Sherloc page "
    "opened in this browser session. Go back, reload the page, and try again. "
    "Answers typed since the page was opened may need to be entered again.</p>"
)


def register_request_guards(app):
    # The token lasts as long as the session. Flask-WTF's default of one hour
    # would refuse a form that stayed open through a long consultation.
    app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)

    @app.errorhandler(CSRFError)
    def _csrf_refused(_error):
        return CSRF_MESSAGE, 400

    @app.before_request
    def _guard_request():
        if _hostname(request.host) not in config.ALLOWED_HOSTS:
            abort(403)

        fetch_site = request.headers.get("Sec-Fetch-Site")
        if fetch_site is not None and fetch_site not in TRUSTED_FETCH_SITES:
            abort(403)

        origin = request.headers.get("Origin")
        if (
            origin is not None
            and request.method not in SAFE_METHODS
            and _origin_hostname(origin) not in config.ALLOWED_HOSTS
        ):
            abort(403)

    # After the guard above, so a foreign Host or Origin is refused first.
    csrf.init_app(app)
