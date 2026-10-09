import json
import config
import os
from inputcheck import validate_serial
from web import app
from web.view.index import get_device
from flask import render_template, request, session, redirect, url_for
from phone_scanner import db
from phone_scanner.db import (
    get_client_devices_from_db,
    new_client_id,
    create_scan,
    create_mult_appinfo,
    first_element_or_none,
)
from debuglog import debug, warn

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
    # clientid = request.form.get('clientid', request.args.get('clientid'))
    if "clientid" not in session:
        return redirect(url_for("index"))

    clientid = session["clientid"]
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

    # clientid = new_client_id()
    debug(">>>scanning_device", device, ser, "<<<<<")

    if device == "ios":
        error = (
            "If an iPhone is connected, open iTunes, click through the "
            'connection dialog and wait for the "Trust this computer" '
            "prompt to pop up in the iPhone, and then scan again."
        )
    else:
        error = (
            "If an Android device is connected, disconnect and reconnect "
            "the device, make sure developer options is activated and USB "
            "debugging is turned on on the device, and then scan again."
        )
    error += (
        "{} <b>Please follow the <a href='/instruction' target='_blank'"
        " rel='noopener'>setup instructions here,</a> if needed.</b>"
    )

    # if device == 'ios':
    #     # go through pairing process and do not scan until it is successful.
    #     isconnected, reason = sc.setup()
    #     template_d["error"] = error.format(reason)
    #     template_d["currently_scanned"] = currently_scanned
    #     if not isconnected:
    #         return render_template("main.html", **template_d), 201

    # TODO: model for 'devices scanned so far:' device_name_map['model']
    # and save it to scan_res along with device_primary_user.
    device_name_print, device_name_map = "<NOT FOUND>", {}
    if from_dump:
        d = db.get_device_info(ser)
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

    scan_d = {
        "clientid": session["clientid"],
        "serial": config.hmac_serial(ser),
        "device": device,
        "device_model": device_name_map.get("model", "<Unknown>").strip(),
        "device_version": device_name_map.get("version", "<Unknown>").strip(),
        "device_primary_user": device_owner,
    }

    if device == "ios":
        scan_d["device_manufacturer"] = "Apple"
        scan_d["last_full_charge"] = "unknown"
    else:
        scan_d["device_manufacturer"] = device_name_map.get(
            "brand", "<Unknown>"
        ).strip()
        scan_d["last_full_charge"] = device_name_map.get(
            "last_full_charge", "<Unknown>"
        )

    debug(f"Getting from dump: {from_dump}")
    if from_dump:
        rooted, rooted_reason = db.get_is_rooted(ser)
    else:
        rooted, rooted_reason = sc.isrooted(ser)
    scan_d["is_rooted"] = rooted
    scan_d["rooted_reasons"] = json.dumps(rooted_reason)

    # TODO: here, adjust client session.
    if from_dump:
        scanid = db.get_most_recent_scan_id(ser)
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
            cmd = os.unlink(pii_fpath)
        # s = catch_err(run_command(cmd), msg="Delete pii failed", cmd=cmd)
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
                "<strong class='text-info'>Maybe (this is possibly just a bug with our scanning tool).</strong> Reason(s): {}".format(
                    rooted_reason
                )
                if rooted
                else "Don't know" if rooted is None else "No"
            ),
            device_name=device_name_print,
            apps=apps,
            scanid=scanid,
            sysapps=set(),  # sc.get_system_apps(serialno=ser)),
            serial=ser,
            currently_scanned=currently_scanned,
            # TODO: make this a map of model:link to display scan results for that
            # scan.
            error=config.error(),
        )
    )
    return render_template("main.html", **template_d), 200
