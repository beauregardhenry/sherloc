from flask import request
import config
from inputcheck import validate_appid, validate_serial
from web import app
from phone_scanner.db import (
    get_serial_from_db,
    update_appinfo,
    get_device_from_db,
)
from web.view.index import get_device
from debuglog import debug, warn


@app.route("/delete/app/<scanid>", methods=["POST"])
def delete_app(scanid):
    appid = request.form.get("appid")
    try:
        validate_appid(appid)
    except ValueError:
        return "Invalid app id.", 400
    device = get_device_from_db(scanid)
    # The database only holds the pseudonymized serial, so the real serial
    # comes from the page. It is accepted only if it is the device that this
    # scan was made on.
    serial = request.form.get("serial", "")
    try:
        validate_serial(serial)
    except ValueError:
        return "Invalid device serial.", 400
    if serial.startswith("HSN_") or config.hmac_serial(serial) != get_serial_from_db(scanid):
        return "That device is not the one this scan was made on.", 400
    sc = get_device(device)
    remark = request.form.get("remark")
    action = "delete"
    r = sc.uninstall(serial=serial, appid=appid)
    if r:
        r = update_appinfo(scanid=scanid, appid=appid, remark=remark, action=action)
        debug("Update appinfo failed! r={}".format(r))
    else:
        warn("Uninstall failed.")
    return is_success(r, "Success!")


def is_success(b, msg_succ="", msg_err=""):
    if b:
        return msg_succ if msg_succ else "Success!", 200
    else:
        return msg_err if msg_err else "Failed", 401
