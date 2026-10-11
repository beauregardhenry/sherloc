from flask import abort, render_template, request

import config
from debuglog import debug
from inputcheck import validate_appid, validate_serial
from scanflow import get_device
from web import app


@app.route("/details/app/<device>", methods=["GET"])
def app_details(device):
    appid = request.args.get("appId")
    ser = request.args.get("serial")
    try:
        validate_appid(appid)
        validate_serial(ser)
    except ValueError:
        return "Invalid app id or device serial.", 400
    sc = get_device(device)
    if sc is None:
        abort(404)
    d, info = sc.app_details(ser, appid)
    d["appId"] = appid


    debug(d.keys())
    return render_template(
        "main.html",
        task="app",
        title=config.TITLE,
        app=d,
        info=info,
        device=device,
    )
