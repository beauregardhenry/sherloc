"""The scan record is built in one place for the classic scan page and the
evidence workflow. They used to carry two copies of the same code, which had
drifted apart (for example, one stored the root-check reason as JSON text and
the other as plain text).
"""

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
import scanrecord


def _record(**kw):
    args = dict(
        clientid="20261010_001",
        ser="ZY224F8TKG",
        device="android",
        device_owner="kitchen phone",
        device_name_map={"model": " Pixel 7 ", "version": " 14 ", "brand": " google ", "last_full_charge": "3h"},
        rooted=False,
        rooted_reason="No indicators.",
    )
    args.update(kw)
    return scanrecord.build_scan_record(**args)


def test_android_record_has_the_database_fields():
    r = _record()
    assert r == {
        "clientid": "20261010_001",
        "serial": config.hmac_serial("ZY224F8TKG"),
        "device": "android",
        "device_model": "Pixel 7",
        "device_version": "14",
        "device_primary_user": "kitchen phone",
        "device_manufacturer": "google",
        "last_full_charge": "3h",
        "is_rooted": False,
        "rooted_reasons": "No indicators.",
    }


def test_the_raw_serial_is_left_out_unless_asked_for():
    assert "serial_or_udid" not in _record()
    assert _record(include_raw_serial=True)["serial_or_udid"] == "ZY224F8TKG"


def test_ios_record_names_apple_and_has_no_charge_time():
    r = _record(device="ios", device_name_map={"model": "iPhone 15", "version": "17.5"})
    assert r["device_manufacturer"] == "Apple"
    assert r["last_full_charge"] == "unknown"


def test_missing_device_details_are_marked_unknown():
    r = _record(device_name_map={})
    assert r["device_model"] == r["device_version"] == r["device_manufacturer"] == "<Unknown>"


@pytest.mark.parametrize(
    "reason,text",
    [("Found 'su binary'.", "Found 'su binary'."), (["a", "b"], "a; b"), ([], ""), (None, "")],
)
def test_root_reason_is_stored_as_plain_text(reason, text):
    assert _record(rooted_reason=reason)["rooted_reasons"] == text


@pytest.mark.parametrize(
    "rooted,label",
    [(True, "Maybe (this is possibly just a bug with our scanning tool). Reason(s): x"), (None, "Don't know"), (False, "No")],
)
def test_rooted_label(rooted, label):
    assert scanrecord.rooted_label(rooted, "x") == label


def test_apps_are_split_into_suspicious_and_other():
    apps = {
        "com.spy": {"title": "Spy", "flags": ["spyware"]},
        "com.dual": {"title": "", "flags": ["onstore-dual-use"]},
        "com.calc": {"title": "Calculator", "flags": []},
    }
    suspicious, other = scanrecord.split_suspicious(apps)
    assert [a["id"] for a in suspicious] == ["com.spy", "com.dual"]
    assert [a["id"] for a in other] == ["com.calc"]
    assert suspicious[1]["app_name"] == "com.dual"  # no title: the app id is shown


def test_both_scan_paths_use_the_shared_record():
    # Both pages scan through scanflow, which builds the record here
    # (tests/test_scanflow.py checks the pages call it).
    import inspect
    import sys

    import evidence_collection
    import scanflow
    import web.view  # noqa: F401

    assert "build_scan_record(" in inspect.getsource(scanflow)
    for mod in (evidence_collection, sys.modules["web.view.scan"]):
        src = inspect.getsource(mod)
        assert "scanflow.run_device_scan(" in src
        assert "'device_manufacturer'" not in src and '"device_manufacturer"' not in src


# --- reading the root check back from the database ----------------------------


def test_get_is_rooted_reads_the_stored_values(tmp_path, monkeypatch):
    from phone_scanner import db as phone_db

    phone_db.init_db(web.app, None)
    with web.app.app_context():
        phone_db.create_scan(_record(rooted=True, rooted_reason="Found 'su binary'."))
        assert phone_db.get_is_rooted(config.hmac_serial("ZY224F8TKG")) == (1, "Found 'su binary'.")
