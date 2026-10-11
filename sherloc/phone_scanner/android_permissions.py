"""
Must work completely from the dumps, no interaction with the device is required.
"""

import datetime
import re

import pandas as pd
from rsonlite import simpleparse

import config
from debuglog import debug
from inputcheck import validate_appid, validate_serial

from .runcmd import run_command


def _parse_time(time_str):
    """
    Parse a time string e.g. (2h13m) into a timedelta object.
    Modified from virhilo's answer at https://stackoverflow.com/a/4628148/851699
    :param time_str: A string identifying a duration.  (eg. 2h13m)
    :return datetime.timedelta: A datetime.timedelta object
        r'^+((?P<days>[\\.\\d]+?)d)?((?P<hours>[\\.\\d]+?)h)?((?P<minutes>[\\.\\d]+?)m)?((?P<seconds>[\\.\\d]+?)s)?((?P<milliseconds>[\\.\\d]+?)ms)?')
    """
    timedelta_re = re.compile(
        r"^.((?P<days>[\.\d]+?)d)?((?P<hours>[\.\d]+?)h)?((?P<minutes>[\.\d]+?)m)?((?P<seconds>[\.\d]+?)s)?((?P<milliseconds>[\.\d]+?)ms)?"
    )
    parts = timedelta_re.match(time_str)
    assert parts is not None, (
        "Could not parse any time information from '{}'."
        "Examples of valid strings: '+8h', '+2d8h5m20s', '+2m4s'".format(time_str)
    )
    time_params = {
        name: float(param) for name, param in parts.groupdict().items() if param
    }
    return datetime.timedelta(**time_params)



def recent_permissions_used(appid, serial):
    """The app's recent app ops, read with adb from the phone being scanned."""
    cols = ["appId", "op", "mode", "timestamp", "time_ago", "duration"]
    df = pd.DataFrame([], columns=cols)
    validate_appid(appid)
    validate_serial(serial)
    # -s: without it adb refuses to run when more than one phone is attached.
    cmd = [config.ADB_PATH, "-s", serial, "shell", "appops", "get", appid]
    recently_used = run_command(cmd).stdout.read().decode("utf-8")

    if "No operations." in recently_used:
        return df

    record = {"appId": appid}
    now = datetime.datetime.now()
    debug(recently_used)
    for permission in recently_used.split("\n")[:-1]:
        permission_attrs = permission.split(";")
        t = permission_attrs[0].split(":")
        if len(t) != 2:  # Could not parse
            continue
        record = {c: "" for c in cols}
        record["op"] = t[0].strip()
        record["mode"] = t[1].strip()
        # "OP: mode; time=+16m12s ago; duration=+10s": the duration is optional.
        if len(permission_attrs) >= 2:
            tt = permission_attrs[1].split("=")
            if len(tt) != 2:
                continue
            record["timestamp"] = (now - _parse_time(tt[1].strip())).strftime(
                config.DATE_STR
            )
            # TODO: keep time_ago? that leaks when the consultation was.
            record["time_ago"] = tt[1].strip()

        if len(permission_attrs) == 3:
            tt = permission_attrs[2].split("=")
            if len(tt) == 2:
                record["duration"] = tt[1].strip()

        df.loc[df.shape[0]] = record
    return df.sort_values(by=["time_ago"]).reset_index(drop=True)


def _indent(line):
    return len(line) - len(line.lstrip(" \t"))


def _package_section(dump_txt, appid):
    """The lines of `Package [appid]` in the dump.

    The section ends at the next line indented no deeper than the
    `Package [` header: the next package, or whatever section follows the
    last package. Read in Python so the app id is never part of a command.
    """
    start = "Package [{}]".format(appid)
    lines = []
    header_indent = None
    with open(dump_txt, errors="replace") as fh:
        for line in fh:
            if header_indent is None:
                if start in line:
                    header_indent = _indent(line)
                    lines.append(line)
            elif line.strip() and _indent(line) <= header_indent:
                break
            else:
                lines.append(line)
    return "".join(lines)


def package_info(dumpf, appid):
    """
    For a specified app, captures lots of package info using sed.
    """

    # FIXME: add check on all permissions, too.
    # need to get
    # requested permissions:
    # install permissions:
    # runtime permissions:
    # This just uses bash to parse something we already have in the dump?
    validate_appid(appid)
    package_dump = _package_section(dumpf.replace(".json", ".txt"), appid)

    # Edge case: Where "Hidden system packages" comes right after a package
    # We need to remove it, otherwise the parsing will fail.
    package_dump = package_dump.split("Hidden system packages")[0]


    sp = None
    try:
        # Parse the package dump (TODO: Look into)
        sp = simpleparse(package_dump)

    except AttributeError:
        debug(package_dump)
        return [], {}

    try:
        # I have no idea what this does.
        #
        # FIXME: TypeError: list indices must be integers or slices, not str
        # FIXME: don't rely on rsonlite to parse correctly? Seems to miss the
        # Packages: section. _package_section() cuts out the one package that
        # is parsed.
        if isinstance(sp, list) and len(sp) > 1:
            sp = sp[0]
        _, pkg = sp.popitem()
        if isinstance(pkg, list):
            pkg = pkg[0]

        install_perms = [
            k.split(":")[0] for k, v in pkg.get("install permissions:", {}).items()
        ]
        requested_perms = pkg.get("requested permissions:", [])

        pkg_info = {}
        pkg_info["firstInstallTime"] = pkg.get("firstInstallTime", "")
        pkg_info["lastUpdateTime"] = pkg.get("lastUpdateTime", "")
        pkg_info["versionCode"] = pkg.get("versionCode", "")
        pkg_info["versionName"] = pkg.get("versionName", "")


        all_perms = list(set(requested_perms) | set(install_perms))
        all_perms.sort()

        return all_perms, pkg_info

    except (IndexError, AttributeError) as e:
        debug(e)
        debug(f"Didn't parse correctly. Not sure why.\nsp={sp}")
        return [], {}


def all_permissions(dumpf, appid, serial):
    """
    Returns a tuple of human-friendly permissions (including recently used), non human-friendly app ops,
    non human-friendly permissions, and summary stats.
    """


    # Apply labels (e.g., "dangerous") to the permissions based on our static list.
    all_static_permissions = pd.read_csv(config.ANDROID_PERMISSIONS_CSV)
    all_static_permissions["label"] = all_static_permissions.apply(
        lambda x: (
            x["permission"].rsplit(".", n=1)[-1] if x["label"] == "null" else x["label"]
        ),
        axis=1,
    )
    
    # Use abd to get the permissions (requested + installed) and package info 
    app_perms, pkg_info = package_info(dumpf, appid)

    # Filter the permissions to only those that are used by the app.
    app_static_permissions = all_static_permissions[
        all_static_permissions["permission"].isin(app_perms)
    ].reset_index(drop=True)
    app_static_permissions["permission_abbrv"] = app_static_permissions.permission.str.rsplit(
        ".", n=1
    ).str[-1]

    ### Now, compare this list with the recently used permissions.

    # Use adb to get the recently used permissions, sorted by time ago (descending)
    recent_permissions = recent_permissions_used(appid, serial)

    # Create a dataframe with the recently-used permissions
    # and the information we have about them in our static list.
    # The human-readable name is "op" or "permission_abbrv"
    # TODO: really 'unknown'?
    hf_recent_permissions = pd.merge(
        recent_permissions,
        app_static_permissions, # Right merge, so keeps all lines from this df
        left_on="op",
        right_on="permission_abbrv",
        how="right",
    ).fillna("Never")

    # Clean up missing data if permission was never used.
    hf_recent_permissions.loc[
        hf_recent_permissions["timestamp"] == "Never", 
        ["mode", "duration"]
    ] = "N/A"
    hf_recent_permissions.loc[
        hf_recent_permissions["appId"] == "Never", 
        "op"
    ] = hf_recent_permissions["permission"]

    # Clean up labels
    hf_recent_permissions["label"] = hf_recent_permissions["label"].apply(
        lambda x: x.capitalize()
    )
    hf_recent_permissions.loc[
        hf_recent_permissions["label"] == "Never",
        "label"
    ] = ""

    # Create a separate list of the recently used permissions
    # that do not have a human-friendly name in our static list.
    # This is done by checking if the "op" is in the "permission_abbrv" column
    # of the app_permissions_tbl.
    no_hf_recent_permissions = recent_permissions[
        ~recent_permissions["op"].isin(app_static_permissions["permission_abbrv"])
    ]

    # Get all the permissions used by the app 
    # that do not have a human-friendly name in our static list.
    no_hf = set(app_perms) - set(app_static_permissions["permission"].tolist())

    stats = {
        "total_permissions": len(app_perms),
        "hf_permissions": app_static_permissions.shape[0],
        "recent_permissions": recent_permissions.shape[0],
        "not_hf_ops": no_hf_recent_permissions.shape[0],
        "not_hf_permissions": len(no_hf),
    }

    return hf_recent_permissions, no_hf_recent_permissions, no_hf, {**stats, **pkg_info}

