import re

import pandas as pd
from blocklist import _regex_blocklist, app_title_and_flag

test_list = [
    ("com.spyware.app", True),
    ("com.antispyware.app", False),
    ("com.spyware-anti.app", True),
    ("com.something.Anti-Spyware.com", False),
    ("com.something.Anti-something-Spyware.com", False),
    ("com.-something-Spyware.com", True),
    ("com.Trackware.com", True),
    ("com.AntiTrackware.com", False),
    ("com.spyware-removal.com", False),
]
regex_pos = r"(?i)(spy|track|keylog)"
regex_neg = r"(?i)(anti.*(spy|track|keylog)|(spy|track|keylog).*remov[ea])"


def test_regex():
    for a, m in test_list:
        assert (re.search(regex_pos, a) and not re.search(regex_neg, a)) == m


def test_blocklist():
    for a, m in test_list:
        assert _regex_blocklist(a) == m


def test_app_title_and_flags():
    d = pd.DataFrame(
        {
            "appId": [
                "core.framework",
                "com.android.system",
                "LEM.TrackMe",
                "com.spy2mobile.light",
            ]
        }
    )
    ret = app_title_and_flag(d, ["core.framework", "com.android.system"]).set_index("appId")
    # This comparison had no `assert`, and the expected text had gone stale.
    assert ret["flags"].to_dict() == {
        "LEM.TrackMe": ["dual-use", "regex-spy"],
        "com.android.system": ["spyware", "offstore-app"],
        "com.spy2mobile.light": ["spyware", "regex-spy"],
        "core.framework": ["spyware", "offstore-app", "regex-spy"],
    }
    assert ret.loc["com.spy2mobile.light", "title"] == "Data Backup"
