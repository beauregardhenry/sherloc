"""The scan record and app lists shared by both scan pages.

The classic scan page (web/view/scan.py) and the evidence workflow
(evidence_collection.get_scan_data) used to build these with two copies of
the same code.
"""

from typing import Any, Optional

import config

SUSPICIOUS_FLAGS = {
    "spyware",
    "dual-use",
    "regex-spy",
    "offstore-spyware",
    "co-occurrence",
    "onstore-dual-use",
    "offstore-app",
}


def reasons_text(reason: Any) -> str:
    """The root-check reason as plain text: a string, or a list joined."""
    if reason is None:
        return ""
    if isinstance(reason, (list, tuple)):
        return "; ".join(str(r) for r in reason)
    return str(reason)


def build_scan_record(
    *,
    clientid: str,
    ser: str,
    device: str,
    device_owner: str,
    device_name_map: dict[str, Any],
    rooted: Optional[bool],
    rooted_reason: Any,
    include_raw_serial: bool = False,
) -> dict[str, Any]:
    """The row stored in `scan_res`. Only the pseudonymized serial is stored."""

    def field(key: str, default: str = "<Unknown>") -> str:
        return str(device_name_map.get(key, default)).strip()

    record: dict[str, Any] = {
        "clientid": clientid,
        "serial": config.hmac_serial(ser),
        "device": device,
        "device_model": field("model"),
        "device_version": field("version"),
        "device_primary_user": device_owner,
    }
    if device == "ios":
        record["device_manufacturer"] = "Apple"
        record["last_full_charge"] = "unknown"
    else:
        record["device_manufacturer"] = field("brand")
        record["last_full_charge"] = device_name_map.get("last_full_charge", "<Unknown>")
    record["is_rooted"] = rooted
    record["rooted_reasons"] = reasons_text(rooted_reason)
    if include_raw_serial:
        # The evidence workflow shows it in the report; it is never stored in the database.
        record["serial_or_udid"] = ser
    return record


def rooted_label(rooted: Optional[bool], reason: Any) -> str:
    if rooted:
        return "Maybe (this is possibly just a bug with our scanning tool). Reason(s): {}".format(
            reasons_text(reason)
        )
    return "Don't know" if rooted is None else "No"


def split_suspicious(apps: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apps with a suspicious flag, and the rest. Each app gets `id` and `app_name`."""
    suspicious: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []
    for appid, app in apps.items():
        app["id"] = appid
        app["app_name"] = app.get("title", "") or appid
        if app["app_name"].strip() == "":
            app["app_name"] = appid
        flags = app.get("flags") or []
        (suspicious if any(f in SUSPICIOUS_FLAGS for f in flags) else other).append(app)
    return suspicious, other
