"""Terminal output that may contain client data.

Notes, client names, device serials and installed-app lists are client data.
Printing them leaves a copy in terminal scrollback, a service journal or a
redirected log file, and "Delete client data" cannot remove those. So the app
prints them only when it runs with DEBUG=1.
"""

import sys
from pprint import pprint
from typing import Any

import config


def debug(*args: Any, **kwargs: Any) -> None:
    """`print`, but only with DEBUG=1."""
    if config.DEBUG:
        print(*args, **kwargs)


def pdebug(obj: Any, *args: Any, **kwargs: Any) -> None:
    """`pprint`, but only with DEBUG=1."""
    if config.DEBUG:
        pprint(obj, *args, **kwargs)


def warn(message: str) -> None:
    """Always print. Only for a fixed message that holds no client data."""
    print(message, file=sys.stderr)
