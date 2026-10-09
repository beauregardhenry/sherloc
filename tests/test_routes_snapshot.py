"""Moving route functions between modules must not change the URLs the app serves."""

from pathlib import Path

import web
import web.view  # noqa: F401


def test_routes_are_unchanged():
    now = sorted(
        f"{r.rule} {sorted(r.methods)} {r.endpoint}" for r in web.app.url_map.iter_rules()
    )
    expected = Path(__file__).with_name("routes_snapshot.txt").read_text().splitlines()
    assert now == expected
