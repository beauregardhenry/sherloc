import json
import config
import os
from inputcheck import validate_serial
from web import app
from web.view.index import get_device
from flask import render_template, request, session, redirect, url_for
from phone_scanner import blocklist, db
from phone_scanner.db import (
    get_client_devices_from_db,
    create_scan,
    create_mult_appinfo,
    first_element_or_none,
)
from debuglog import debug, warn
from scanrecord import build_scan_record, rooted_label

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
        device_primary_user=config.DEVICE_PRIMARY_USER,  # TODO: Why is this sent
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

    if not ser:
        ser = first_element_or_none(sc.devices())
    if ser:
        try:
            validate_serial(ser)
        except ValueError:
            template_d["error"] = "The device reported a serial number that Sherloc cannot use."
            return render_template("main.html", **template_d), 201

    debug("Devices: {}".format(ser))
    if not ser:
        # FIXME: add pkexec scripts/ios_mount_linux.sh workflow for iOS if
        # needed.
        error = (
            "<b>A device wasn't detected. Please follow the "
            "<a href='/instruction' target='_blank' rel='noopener'>"
            "setup instructions here.</a></b>"
        )
        template_d["error"] = error
        return render_template("main.html", **template_d), 201

    debug(">>>scanning_device", device, ser, "<<<<<")

    # TODO: model for 'devices scanned so far:' device_name_map['model']
    # and save it to scan_res along with device_primary_user.
    device_name_print, device_name_map = "<NOT FOUND>", {}
    if from_dump:
        # The database holds only the pseudonymized serial.
        d = db.get_device_info(config.hmac_serial(ser))
        if d:
            debug(d)
            device_name_print = f"{d['device_model']} ({d['device_primary_user']})"
            device_name_map = d
        else:
            debug("ERROR: Could not find device info:", d)
    else:
        device_name_print, device_name_map = sc.device_info(serial=ser)

    # Finds all the apps in the device
    # @apps have appid, title, flags, TODO: add icon
    apps = (
        sc.find_spyapps(serialno=ser, from_dump=from_dump)
        .fillna("")
        .to_dict(orient="index")
    )
    if len(apps) <= 0:
        warn("The scanning failed for some reason.")
        error = (
            "The scanning failed. This could be due to many reasons. Try"
            " rerunning the scan from the beginning. If the problem persists,"
            " please report it in the file. <code>report_failed.md</code> in the<code>"
            "phone_scanner/</code> directory. Checn the phone manually. Sorry for"
            " the inconvenience."
        )
        template_d["error"] = error
        return render_template("main.html", **template_d), 201

    debug(f"Getting from dump: {from_dump}")
    if from_dump:
        rooted, rooted_reason = db.get_is_rooted(config.hmac_serial(ser))
    else:
        rooted, rooted_reason = sc.isrooted(ser)
    scan_d = build_scan_record(
        clientid=session["clientid"],
        ser=ser,
        device=device,
        device_owner=device_owner,
        device_name_map=device_name_map,
        rooted=rooted,
        rooted_reason=rooted_reason,
    )

    # TODO: here, adjust client session.
    if from_dump:
        scanid = db.get_most_recent_scan_id(config.hmac_serial(ser))
        if scanid == -1:
            template_d["error"] = (
                "The serial number provided does not have a scan yet, "
                "and you want to read from the dump. Please connect the device and scan first."
            )
            return render_template("main.html", **template_d), 201
    else:
        scanid = create_scan(scan_d)

    if device == "ios":
        pii_fpath = sc.dump_path(ser, "Device_Info")
        debug("Revelant info saved to db. Deleting {} now.".format(pii_fpath))
        if os.path.exists(pii_fpath):
            os.unlink(pii_fpath)
        debug("iOS PII deleted.")

    debug("Creating appinfo...")
    create_mult_appinfo(
        [
            (scanid, appid, json.dumps(info["flags"]), "", "<new>")
            for appid, info in apps.items()
        ]
    )

    currently_scanned = get_client_devices_from_db(session["clientid"])
    template_d.update(
        dict(
            isrooted=(
                "<strong class='text-info'>{}</strong>".format(rooted_label(rooted, rooted_reason))
                if rooted
                else rooted_label(rooted, rooted_reason)
            ),
            device_name=device_name_print,
            apps=apps,
            scanid=scanid,
            sysapps=set(),  # sc.get_system_apps(serialno=ser)),
            serial=ser,
            currently_scanned=currently_scanned,
        )
    )
    return render_template("main.html", **template_d), 200
