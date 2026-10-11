import sqlite3
import clientwords
import config
from flask import g
from datetime import datetime as dt
import os
from debuglog import debug


def database_path():
    return config.SQL_DB_PATH.replace("sqlite:///", "").strip()


def today():
    return dt.now().strftime("%Y%m%d")


def new_client_id():
    """A new client ID: four random words, not used by any intake form or scan."""

    def taken(cid):
        return bool(query_db(
            "select 1 from clients_notes where clientid = ? "
            "union select 1 from scan_res where clientid = ?",
            args=(cid, cid),
        ))

    return clientwords.make_client_id(taken)


def make_dicts(cursor, row):
    return dict((cursor.description[idx][0], value) for idx, value in enumerate(row))


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        debug("Creating new db connection {}".format(database_path()))
        db = g._database = sqlite3.connect(database_path())
        db.row_factory = make_dicts
    return db


def init_db(app, sa, force=False):
    """Create the tables. schema.sql only uses IF NOT EXISTS, so it is safe to
    run on every start, and it adds tables that a database from an earlier
    version does not have yet."""
    with app.app_context():
        os.makedirs(os.path.dirname(database_path()), mode=0o700, exist_ok=True)
        db = get_db()
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()


def insert(query, args):
    db = get_db()
    cur = db.execute(query, args)
    lrowid = cur.lastrowid
    cur.close()
    db.commit()
    return lrowid


def insert_many(query, argss):
    db = get_db()
    cur = db.executemany(query, argss)
    lrowid = cur.lastrowid
    cur.close()
    db.commit()
    return lrowid


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def create_scan(scan_d):
    """
    @scanr must have following fields.
    """
    debug(scan_d)
    return insert(
        "insert into scan_res "
        "(clientid, serial, device, device_model, device_version, device_manufacturer, last_full_charge, device_primary_user, is_rooted, rooted_reasons) "
        "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        args=(
            scan_d["clientid"],
            scan_d["serial"],
            scan_d["device"],
            scan_d["device_model"],
            scan_d["device_version"],
            scan_d["device_manufacturer"],
            scan_d["last_full_charge"],
            scan_d["device_primary_user"],
            scan_d["is_rooted"],
            scan_d["rooted_reasons"],
        ),
    )


def update_appinfo(scanid, appid, remark, action):
    return (
        insert(
            "update app_info set "
            "remark=?, action_taken=? where scanid=? and appid=?",
            args=(remark, action, scanid, appid),
        )
        == 0
    )


def create_mult_appinfo(args):
    """ """
    return insert_many(
        "insert into app_info (scanid, appid, flags, remark, action_taken) values (?,?,?,?,?)",
        args,
    )


def get_is_rooted(serial):
    try:
        d = query_db(
            "select id, is_rooted, rooted_reasons from scan_res where serial=?",
            args=(serial,),
            one=False,
        )
        if d:
            d = d[0]
        return d["is_rooted"], d["rooted_reasons"]
    except Exception:
        return "<ROOTED_ERR>", "<ROOTED_ERR>"


def get_device_info(ser: str) -> dict:
    d = query_db(
        "select id,device,device_model,serial,device_primary_user from scan_res where serial=?",
        args=(ser,),
        one=True,
    )
    if d:
        return d
    else:
        return {}


def get_client_devices_from_db(clientid: str) -> list:
    """The devices scanned for this client, one row per device."""
    d = query_db(
        "select id,device,device_model,serial,device_primary_user from scan_res "
        "where clientid=? and serial like 'HSN_%' group by serial",
        args=(clientid,),
        one=False,
    )
    debug("<>get_client_devices_from_db<>", d)
    return d or []


def get_most_recent_scan_id(ser: str) -> int:
    d = query_db(
        "select max(id) as scanid from scan_res where serial=?", args=(ser,), one=True
    )
    debug(f"Get_most_recent_scanid: {d}")
    # max() over no rows is NULL; callers check for -1.
    return d["scanid"] if d and d["scanid"] is not None else -1


def get_device_from_db(scanid):
    d = query_db("select device from scan_res where id=?", args=(scanid,), one=True)
    if d:
        return d["device"]
    else:
        return ""


def get_serial_from_db(scanid):
    d = query_db("select serial from scan_res where id=?", args=(scanid,), one=True)
    if d:
        return d["serial"]
    else:
        return ""


