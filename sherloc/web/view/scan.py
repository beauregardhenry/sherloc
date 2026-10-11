import config
import os
from inputcheck import validate_serial
from web import app
from web.view.index import get_device
from flask import render_template, request, session, redirect, url_for
from phone_scanner import blocklist
from phone_scanner.db import (
    get_client_devices_from_db,
)
from debuglog import debug
import scanflow
from scanrecord import rooted_label

@app.template_filter("flag_class")
def flag_class(flags):
    """The Bootstrap alert class for an app's row, from its flags' weight."""
    w = blocklist.score(flags or [])
    norm_w = 0 if w <= 0 else 1 if w <= 0.3 else 2 if w <= 0.8 else 3
    return ["", "alert-info", "alert-warning", "alert-primary"][norm_w]


def get_param(key):
    return request.form.get(key, request.args.get(key))


@app.route("/scan", methods=["POST", "GET"])
def scan():
    """
    Needs three attribute for a device
    :param device: "android" or "ios" or test
    :param devid: id of the android device
    :param cientid: id of the cient
    :return: a flask view template
    """
    if "clientid" not in session:
        return redirect(url_for("index"))

    device_primary_user = get_param("device_primary_user")
    device = get_param("device")
    action = get_param("action")
    device_owner = get_param("device_owner")
    ser = get_param("devid")
    if ser:
        try:
            validate_serial(ser)
        except ValueError:
            return "Invalid device serial.", 400
    t_from_dump = get_param("from_dump")
    from_dump = False
    if t_from_dump:
        try:
            from_dump = int(t_from_dump)
        except ValueError:
            from_dump = False

    currently_scanned = get_client_devices_from_db(session["clientid"])
    template_d = dict(
        task="home",
        title=config.TITLE,
        device=device,
        device_primary_user_sel=device_primary_user,
        apps={},
        currently_scanned=currently_scanned,
        clientid=session["clientid"],
    )
    # lookup devices scanned so far here. need to add this by model rather
    # than by serial.
    debug("CURRENTLY SCANNED: {}".format(currently_scanned))
    debug("DEVICE OWNER IS: {}".format(device_owner))
    debug("PRIMARY USER IS: {}".format(device_primary_user))
    debug("SERIAL NO: {}".format(ser))
    debug("FROM DUMP: {}".format(from_dump))
    debug("-" * 80)
    debug("CLIENT ID IS: {}".format(session["clientid"]))
    debug("-" * 80)
    debug("--> Action = ", action)

    sc = get_device(device)
    if not sc:
        template_d["error"] = "Please choose one device to scan."
        return render_template("main.html", **template_d), 201
    if not device_owner:
        template_d["error"] = "Please give the device a nickname."
        return render_template("main.html", **template_d), 201

    try:
        ser = scanflow.find_serial(sc, ser)
    except scanflow.ScanFailed as e:
        if str(e) == scanflow.NO_DEVICE:
            # FIXME: add pkexec scripts/ios_mount_linux.sh workflow for iOS if needed.
            template_d["error"] = (
                "<b>A device wasn't detected. Please follow the "
                "<a href='/instruction' target='_blank' rel='noopener'>"
                "setup instructions here.</a></b>"
            )
        else:
            template_d["error"] = str(e)
        return render_template("main.html", **template_d), 201

    debug(">>>scanning_device", device, ser, "<<<<<")

    try:
        result = scanflow.run_device_scan(
            sc,
            device=device,
            ser=ser,
            device_owner=device_owner,
            clientid=session["clientid"],
            from_dump=from_dump,
        )
    except scanflow.ScanFailed as e:
        template_d["error"] = str(e)
        return render_template("main.html", **template_d), 201
    rooted, rooted_reason = result.rooted, result.rooted_reason

    if device == "ios":
        # The device info is in the database now; the dump file holds PII.
        pii_fpath = sc.dump_path(ser, "Device_Info")
        if os.path.exists(pii_fpath):
            os.unlink(pii_fpath)
        debug("iOS PII deleted.")

    currently_scanned = get_client_devices_from_db(session["clientid"])
    template_d.update(
        dict(
            isrooted=(
                "<strong class='text-info'>{}</strong>".format(rooted_label(rooted, rooted_reason))
                if rooted
                else rooted_label(rooted, rooted_reason)
            ),
            device_name=result.device_name,
            apps=result.apps,
            scanid=result.scanid,
            sysapps=set(),  # sc.get_system_apps(serialno=ser)),
            serial=ser,
            currently_scanned=currently_scanned,
        )
    )
    return render_template("main.html", **template_d), 200
