"""The scan steps shared by both scan pages (issue #20).

The classic scan page (web/view/scan.py) and the evidence workflow
(evidence_collection.get_scan_data) each read the device, found its apps and
saved the scan, with two copies of the code. Both call `run_device_scan` now.
"""

import json
from dataclasses import dataclass
from typing import Any, Optional

import config
from debuglog import debug, warn
from inputcheck import validate_serial
from phone_scanner import db
from scanrecord import build_scan_record

NO_APPS = (
    "The scanning failed. This could be due to many reasons. Try rerunning the"
    " scan from the beginning. If the problem persists, check the phone manually."
    " Sorry for the inconvenience."
)
NO_DEVICE = "A device wasn't detected."
BAD_SERIAL = "The device reported a serial number that Sherloc cannot use."
NO_EARLIER_SCAN = (
    "The serial number provided does not have a scan yet, and you want to read"
    " from the dump. Please connect the device and scan first."
)


class ScanFailed(Exception):
    """The scan could not be completed. The message is shown to the consultant."""


@dataclass
class ScanResult:
    scan: dict[str, Any]
    scanid: int
    apps: dict[str, dict[str, Any]]
    device_name: str
    rooted: Optional[bool]
    rooted_reason: Any


def find_serial(sc: Any, ser: Optional[str] = None) -> str:
    """The serial to scan: `ser` if given, else the first connected device.

    The serial goes to device commands, so it is checked either way.
    """
    if not ser:
        connected = sc.devices()
        debug("Devices: {}".format(connected))
        ser = connected[0] if connected else None
    if not ser:
        raise ScanFailed(NO_DEVICE)
    try:
        validate_serial(ser)
    except ValueError:
        raise ScanFailed(BAD_SERIAL) from None
    return ser


def _device_info(sc: Any, ser: str, from_dump: bool) -> tuple[str, dict[str, Any]]:
    if not from_dump:
        name, info = sc.device_info(serial=ser)
        return name, info
    # The database holds only the pseudonymized serial.
    d = db.get_device_info(config.hmac_serial(ser))
    if not d:
        debug("Could not find device info for the dump.")
        return "<NOT FOUND>", {}
    return f"{d['device_model']} ({d['device_primary_user']})", d


def run_device_scan(
    sc: Any,
    *,
    device: str,
    ser: str,
    device_owner: str,
    clientid: str,
    from_dump: bool = False,
    include_raw_serial: bool = False,
) -> ScanResult:
    """Read the device and its apps, then save the scan and the app list.

    With `from_dump`, the device info, root check and scan id come from the
    earlier scan of this device instead of the phone. Raises `ScanFailed`
    before anything is saved when no apps are found or there is no earlier
    scan to read from.
    """
    device_name, device_info = _device_info(sc, ser, from_dump)

    apps = sc.find_spyapps(serialno=ser, from_dump=from_dump).fillna("").to_dict(orient="index")
    if not apps:
        warn("The scanning failed for some reason.")
        raise ScanFailed(NO_APPS)

    if from_dump:
        rooted, rooted_reason = db.get_is_rooted(config.hmac_serial(ser))
    else:
        rooted, rooted_reason = sc.isrooted(ser)

    scan = build_scan_record(
        clientid=clientid,
        ser=ser,
        device=device,
        device_owner=device_owner,
        device_name_map=device_info,
        rooted=rooted,
        rooted_reason=rooted_reason,
        include_raw_serial=include_raw_serial,
    )

    if from_dump:
        scanid = db.get_most_recent_scan_id(config.hmac_serial(ser))
        if scanid == -1:
            raise ScanFailed(NO_EARLIER_SCAN)
    else:
        scanid = db.create_scan(scan)

    db.create_mult_appinfo(
        [(scanid, appid, json.dumps(info["flags"]), "", "<new>") for appid, info in apps.items()]
    )
    return ScanResult(scan, scanid, apps, device_name, rooted, rooted_reason)
