#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime

import config
import pandas as pd

from . import blocklist, parse_dump
from .android_permissions import all_permissions
from .runcmd import catch_err, run_checked, run_command
from inputcheck import validate_appid, validate_serial
from debuglog import debug, warn


class AppScan(object):
    device_type = ""
    app_info_conn = sqlite3.connect(
        config.APP_INFO_SQLITE_FILE.replace("sqlite:///", ""), check_same_thread=False
    )

    def __init__(self, dev_type, cli):
        assert (
            dev_type in config.DEV_SUPPRTED
        ), "dev={!r} is not supported yet. Allowed={}".format(
            dev_type, config.DEV_SUPPRTED
        )
        self.device_type = dev_type
        self.cli = cli  # The cli of the device, e.g., adb or mobiledevice
        self.parse_dump = None  # Only here to please the linter

    def setup(self):
        """If the device needs some setup to work."""
        pass

    def devices(self):
        raise Exception("Not implemented")

    def get_system_apps(self, serialno, from_device: bool) -> list:
        pass

    def get_apps(self, serialno: str, from_dump: bool) -> list:
        pass

    def get_offstore_apps(self, serialno: str, from_dump: bool) -> list:
        return []

    def get_app_titles(self, serialno):
        return []

    def dump_path(self, serial, fkind="json"):
        hmac_serial = config.hmac_serial(serial)
        if self.device_type == "ios":
            devicedumpsdir = os.path.join(
                config.DUMP_DIR, "{}_{}".format(hmac_serial, "ios")
            )
            if fkind == "Jailbroken-FS":
                return os.path.join(
                    devicedumpsdir, config.IOS_DUMPFILES.get("Jailbroken-FS", "")
                )
            elif fkind == "Jailbroken-SSH":
                return os.path.join(
                    devicedumpsdir, config.IOS_DUMPFILES.get("Jailbroken-SSH", "")
                )
            elif fkind == "Device_Info":
                return os.path.join(
                    devicedumpsdir, config.IOS_DUMPFILES.get("Info", "")
                )
            elif fkind == "Apps":
                return os.path.join(
                    devicedumpsdir, config.IOS_DUMPFILES.get("Apps", "")
                )
            elif fkind == "Dir":
                return devicedumpsdir
            else:
                # returns apps dumpfile if fkind isn't explicitly specified.
                return os.path.join(
                    devicedumpsdir, config.IOS_DUMPFILES.get("Apps", "")
                )

        return os.path.join(
            config.DUMP_DIR, "{}_{}.{}".format(hmac_serial, self.device_type, fkind)
        )

    def app_details(self, serialno, appid) -> tuple[dict, dict]:
        try:
            # Read the database and get info about this app
            # TODO: Stop using the database
            d = pd.read_sql(
                "select * from apps where appid=?", self.app_info_conn, params=(appid,)
            )

            # Ensure the permissions attribute is a list
            if not isinstance(d.get("permissions", ""), list):
                d["permissions"] = d.get("permissions", pd.Series([]))
                d["permissions"] = d["permissions"].fillna("").str.split(", ")

            # Update descriptionHTML
            if "descriptionHTML" not in d:
                d["descriptionHTML"] = d["description"]

            # Parse the dump to get dump info (which includes..?)
            dfname = self.dump_path(serialno)
            if self.device_type == "ios":
                ddump = self.parse_dump
                if not ddump:
                    ddump = parse_dump.IosDump(dfname)
            else:
                ddump = parse_dump.AndroidDump(dfname)
            info = ddump.info(appid)

            config.logging.info("BEGIN APP INFO")
            config.logging.info("info={}".format(info))
            config.logging.info("END APP INFO")

            # For Android, combine permissions together
            # We start with three types: runtime, declared, install
            if self.device_type == "android":
                # declared and install are regular
                # runtime is nested under "User ...."
                pass

            # FIXME: sloppy iOS hack but should fix later, just add these to DF
            # directly.
            if self.device_type == "ios":
                # TODO: add extra info about iOS? Like idevicediagnostics
                # ioregentry AppleARMPMUCharger or IOPMPowerSource or
                # AppleSmartBattery.
                d["permissions"] = pd.Series(info.get("permissions", []), dtype=object)
                d["title"] = pd.Series(info.get("title", ""))

            d = d.fillna("").to_dict(orient="index").get(0, {}) # what does this do?

            if self.device_type == "ios":
                d["permissions"] = info.get("permissions", [])
                d["title"] = info.get("title", "")

                # TEMP FIX: mask InfoPlist.strings references
                old_permissions = d.get("permissions", []) 
                new_permissions = []

                for perm, reason in old_permissions:
                    if "permission granted by system" in reason.lower():
                        reason = "[system permission]"
                    elif "infoplist.strings" in reason.lower():
                        reason = "[description not available]"
                    elif "NSLocationWhenInUseUsageDescriptionUndefined".lower() in reason.lower():
                        reason = "[description not available]"
                    
                    new_permissions.append((perm, reason))

                d["permissions"] = new_permissions

            return d, info
        
        except KeyError as ex:
            debug(">>> Exception:::", ex, file=sys.stderr)
            return dict(), dict()

    def find_spyapps(self, serialno, from_dump=False):
        """Finds the apps in the phone and add flags to them based on @blocklist.py
        Return the sorted dataframe
        This is the **main** function that is called from the views in web/view/scan.py
        """
        installed_apps = self.get_apps(serialno, from_dump=from_dump)

        if len(installed_apps) <= 0:
            return pd.DataFrame(
                [], columns=["title", "flags", "score", "html_flags"]
            )
        r = blocklist.app_title_and_flag(
            pd.DataFrame({"appId": installed_apps}),
            offstore_apps=self.get_offstore_apps(serialno, from_dump=from_dump),
            system_apps=self.get_system_apps(serialno, from_dump=from_dump),
        )
        r["title"] = r.title.fillna("")
        if self.device_type == "android":
            td = pd.read_sql(
                "select appid as appId, title from apps where appid in (?{})".format(
                    ", ?" * (len(installed_apps) - 1)
                ),
                self.app_info_conn,
                params=(installed_apps),
                index_col="appId",
            )
            td.index.rename("appId", inplace=True)
        elif self.device_type == "ios":
            td = self.get_app_titles(serialno)

        r.set_index("appId", inplace=True)
        td = td.loc[:, ~td.columns.duplicated()]
        r.loc[td.index, "title"] = td.get("title", "")
        r.reset_index(inplace=True)

        r["score"] = r["flags"].apply(blocklist.score)
        r["title"] = r.title.str.encode("ascii", errors="ignore").str.decode("ascii")
        r["title"] = r.title.fillna("")
        r["html_flags"] = r["flags"].apply(blocklist.flag_str)
        r.sort_values(
            by=["score", "appId"],
            ascending=[False, True],
            inplace=True,
            na_position="last",
        )
        r.set_index("appId", inplace=True)

        return r[["title", "flags", "score", "html_flags"]]

    def flag_apps(self, serialno):
        installed_apps = self.get_apps(serialno, from_dump=False)
        app_flags = blocklist.flag_apps(installed_apps)
        return app_flags

    def uninstall(self, serial, appid):
        pass

    def save(self, table, **kwargs):
        return False

    def device_info(self, serial):
        return "Test Phone", {}

    def isrooted(self, serial):
        return (False, [])


class AndroidScan(AppScan):
    """NEED Android Debug Bridge (adb) tool installed. Ensure your Android device
    is connected through Developer Mode with USB Debugging enabled, and `adb
    devices` showing the device as connected before running this scan function.

    """

    def __init__(self):
        super(AndroidScan, self).__init__("android", config.ADB_PATH)
        self.serialno = None
        self.installed_apps = None
        self.dump_d = None

    def setup(self):
        """Restart the adb server."""
        for action in ("kill-server", "start-server"):
            # The server keeps running after `start-server` returns, so its
            # output is not captured: a pipe it holds open would block us.
            try:
                done = subprocess.run(
                    [self.cli, action],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as ex:
                warn(f">> adb {action} failed: {ex!r}")
                continue
            if done.returncode != 0:
                debug(
                    f">> adb {action} failed with returncode={done.returncode}",
                    file=sys.stderr,
                )

    def _get_apps_from_device(self, serialno, flag) -> list:
        """
        Uses adb to list packages on the device. 
        Returns the list of installed packages.
        """

        validate_serial(serialno)
        cmd = [self.cli, "-s", serialno, "shell", "pm", "list", "packages", *flag.split()]
        p = run_command(cmd)
        s = catch_err(p, msg="App search failed", cmd=" ".join(cmd))
        # catch_err returns an error message when the command fails, so the
        # exit status decides whether `s` is a package list.
        if p.returncode != 0 or not s:
            self.setup()
            return []
        else:
            lines = (re.sub(r"^package:", "", x) for x in s.splitlines())
            return sorted(x for x in lines if x)

    def _get_apps_from_dump(self, hmac_serial):
        """Parses the dump file to get the list of installed apps."""

        # Read from dump and put the data in self.dump_d
        dump_file = self.dump_path(hmac_serial)
        self.dump_d = parse_dump.AndroidDump(dump_file)

        # Uses dump_d (the AndroidDump obj) to get the app information
        app_and_codes = self.dump_d.apps()

        # Return just the list of app names
        return [a for a, c in app_and_codes]

    def get_apps(self, serialno: str, from_dump: bool = False) -> list:
        """Returns the list of installed apps on the device."""

        validate_serial(serialno)
        debug(f"Getting Android apps: {serialno} from_dump={from_dump}")
        hmac_serial = config.hmac_serial(serialno)
        if not from_dump:
            # Get list of installed packages using adb
            installed_apps = self._get_apps_from_device(serialno, "-u")

            # If the list is non-empty, run a full scan 
            # (TODO: When would this be empty?)
            if installed_apps:
                run_command(
                    ["bash", "scripts/android_scan.sh", "scan", serialno, hmac_serial],
                    nowait=True,
                )
        else:
            # Try loading from the dump
            installed_apps = self._get_apps_from_dump(hmac_serial)
        self.installed_apps = installed_apps
        return installed_apps

    def get_system_apps(self, serialno, from_dump=False) -> list:
        if not from_dump:
            apps = self._get_apps_from_device(serialno, "-s")
        else:
            apps = []  # TODO: fix this later, not sure how to get from dump
        return apps

    def get_offstore_apps(self, serialno, from_dump=False) -> list:
        if from_dump:
            return []  # TODO: fix this later, not sure how to get from dump
        offstore = []
        rooted, reason = self.isrooted(serialno)
        approved = config.APPROVED_INSTALLERS
        if not rooted:
            for line in self._get_apps_from_device(serialno, "-i -u -s"):
                line = line.split()
                if len(line) == 2:
                    apps, t = line
                    installer = t.replace("installer=", "")
                    if installer not in approved and installer != "null":
                        # if system is rooted, won't make any difference spoofing wise
                        approved.add(installer)
        debug(f"Approved Installers:{approved}")
        for line in self._get_apps_from_device(serialno, "-i -u -3"):
            line = line.split()
            if len(line) == 2:
                apps, t = line
                installer = t.replace("installer=", "")
                if installer not in approved:
                    offstore.append(apps)
            else:
                debug(">>>>>> ERROR: {}".format(line), file=sys.stderr)
        return offstore

    def devices(self):
        cmd = [self.cli, "devices"]
        p = run_command(cmd)
        output = catch_err(p, cmd=" ".join(cmd))
        if p.returncode != 0:
            return []
        # The first line is the "List of devices attached" header.
        runcmd = output.strip().split("\n")[1:]
        conn_devices = []
        for rc in runcmd:
            d = rc.split()
            if len(d) != 2:
                continue
            device, state = rc.split()
            device = device.strip()
            if state.strip() == "device":
                try:
                    validate_serial(device)
                except ValueError:
                    # The serial is reported by the device. Do not use one
                    # that could not be passed safely to a command.
                    debug("Ignoring a device with an unusable serial number.")
                    continue
                conn_devices.append(device)
        return conn_devices


    def _getprop(self, serial, prop):
        p = run_command([self.cli, "-s", serial, "shell", "getprop", prop])
        return p.stdout.read().decode("utf-8").strip()

    def device_info(self, serial):
        validate_serial(serial)
        m = {}
        m["brand"] = self._getprop(serial, "ro.product.brand").title()
        m["model"] = self._getprop(serial, "ro.product.model")
        m["version"] = self._getprop(serial, "ro.build.version.release")
        m["last_full_charge"] = datetime.now()
        return "{brand} {model} (running Android {version})".format(**m), m


    def uninstall(self, serial, appid):
        validate_appid(appid)
        validate_serial(serial)
        # `-s` targets the device that was scanned; without it adb refuses to
        # run when more than one device is attached.
        ok, _ = run_checked([self.cli, "-s", serial, "uninstall", appid])
        return ok

    def app_details(self, serialno, appid) -> tuple[dict, dict]:

        # First, get basic app details using the Super class
        d, info = super(AndroidScan, self).app_details(serialno, appid)

        # runtime/install/declared permissions

        # Then, get more details about permissions
        # This requires the phone to be connected
        hf_recent, non_hf_recent, non_hf, stats = all_permissions(
            self.dump_path(serialno), appid
        )
        # FIXME: some appopps in non_hf_recent are not included in the
        # output.  maybe concat hf_recent with them?
        info["install_time"] = stats.get("firstInstallTime", "")
        info["last_updated"] = stats.get("lastUpdateTime", "")

        info["app_version"] = stats.get("versionName", "")

        # hf_recent['label'] = hf_recent[['label',
        # 'timestamp']].apply(lambda x: ''.join(str(x), axis=1))

        # Format recent permissions as (label, timestamp) tuples
        # If the label is empty, just use the permission
        # If the label is not empty, use "<label> (<permission_abbrv>)"
        labeled_permissions = []
        unlabeled_permissions = []
        permission_info_tmp = list(zip(hf_recent["label"].tolist(), 
                                       hf_recent["permission"].to_list(), 
                                       hf_recent["permission_abbrv"].to_list(),
                                       hf_recent["timestamp"].tolist()))
        for tup in permission_info_tmp:
            label, permission, permission_abbrv, timestamp = tup
            if label:
                # If label is not empty, use it with the permission abbreviation
                labeled_permissions.append((f"{label} ({permission_abbrv})",
                                         f"Last used: {timestamp}"))
            else:
                # If label is empty, just use the permission
                unlabeled_permissions.append((permission, 
                                         f"Last used: {timestamp}"))
                
        # Combine with labeled permissions listed first
        # TODO: Should we also get the non-hf permissions? 
        # it's just ignoring those for now...
        d["permissions"] = labeled_permissions + unlabeled_permissions
                
        

 
        non_hf_recent.drop("appId", axis=1, inplace=True)

        d["non_hf_permissions_html"] = non_hf_recent.to_html()

        return d, info

    def isrooted(self, serial):
        """
        Doesn't return all reasons by default. First match will return.
        TODO: make consistent with iOS isrooted, which returns all reasons discovered.
        """
        validate_serial(serial)
        # FIXME: load these from a private database instead.  from OWASP,
        # https://sushi2k.gitbooks.io/the-owasp-mobile-security-testing-guide/content/0x05j-Testing-Resiliency-Against-Reverse-Engineering.html

        root_pkgs_check_str = "\\|".join(
            [
                "com.noshufou.android.su",
                "com.thirdparty.superuser",
                "eu.chainfire.supersu",
                "com.koushikdutta.superuser",
                "com.zachspong.temprootremovejb",
                "com.ramdroid.appquarantine",
            ]
        )
        root_checks = {
            "su binary": ("command -v su", "0"),
            "oem unlock": ("getprop ro.boot.flash.locked", "0"),
            "frida server": ("ps -A | grep frida", "0"),
            "root_pkgs": (f"pm list packages | grep {root_pkgs_check_str}", "0"),
        }
        for k, v in root_checks.items():
            # The check runs in the device's shell, so it is one argument.
            cmd = [self.cli, "-s", serial, "shell", v[0]]
            s = catch_err(run_command(cmd), cmd=" ".join(cmd))
            if s.strip() == v[1]:
                return (True, f"The device is rooted: Found:  {k!r}.")
        return (False, "Automated checks were run to check: su binaries, OEM unlock, Frida, and the presence of various root packages. There were no indicators that the device is rooted.")


class IosScan(AppScan):
    """
    Run `bash scripts/setup.sh to get libimobiledevice dependencies`
    """

    def __init__(self):
        super(IosScan, self).__init__("ios", cli=config.LIBIMOBILEDEVICE_PATH)
        self.installed_apps = None
        self.serialno = None
        self.parse_dump = None

    def setup(self, attempt_remount=False):
        """FIXME: iOS setup."""
        return (True, "Follow trust dialog on iOS device to continue.")

    # TODO: This might send titles out of order. Fix this to send both appid and
    # titles.
    def get_app_titles(self, serialno):
        if not self.parse_dump:
            self._dump_phone(serialno)
        return self.parse_dump.installed_apps_titles()

    def get_apps(self, serialno: str, from_dump: bool) -> list:
        """iOS always read everything from dump, so nothing to change."""
        debug("inside get_apps()")
        self.serialno = serialno
        if not from_dump:
            if not self._dump_phone(serialno):
                warn("Failed to dump the phone.")
                return []
        debug("before _load_dump()")
        self._load_dump(serialno)
        debug("after _load_dump()")
        self.installed_apps = self.parse_dump.installed_apps()
        debug("iOS INFO DUMPED.")
        return self.installed_apps

    def get_system_apps(self, serialno: str, from_dump: bool) -> list:
        if self.parse_dump:
            return self.parse_dump.system_apps()
        else:
            return []

    def devices(self):
        def _is_device(x):
            """Is it looks like a serial number"""
            try:
                validate_serial(x)
            except ValueError:
                return False
            return re.match(r"[a-f0-9]+", x) is not None

        cmd = ["pymobiledevice3", "usbmux", "list"]

        self.serialno = None
        p = run_command(cmd)
        listing = catch_err(p, cmd=" ".join(cmd), msg="")
        if p.returncode != 0:
            return []
        # The value of each "Identifier" line: `"Identifier": "<udid>",`
        s = "\n".join(
            line.split('"')[3]
            for line in listing.splitlines()
            if "Identifier" in line and line.count('"') >= 4
        )

        d = [
            line.strip()
            for line in s.split("\n")
            if line.strip() and _is_device(line.strip())
        ]
        config.logging.info("Devices found:", d)
        return d

    def device_info(self, serial):
        dumped = self._dump_phone(serial)
        self._load_dump(serial)
        if dumped:
            device_info_print, device_info_map = self.parse_dump.device_info()
            return (device_info_print, device_info_map)
        else:
            return ("", {})

    def _load_dump(self, serial) -> parse_dump.IosDump:
        path = self.dump_path(serial, fkind="Dir")
        dumpf = os.path.join(path, config.IOS_DUMPFILES["Apps"])
        dumpfinfo = os.path.join(path, config.IOS_DUMPFILES["Info"])
        self.parse_dump = parse_dump.IosDump(dumpf, finfo=dumpfinfo)
        return self.parse_dump

    def _dump_phone(self, serial: str) -> bool:
        debug("DUMPING iOS INFO...")
        connected, connected_reason = self.setup()
        if not connected:
            warn("Couldn't connect to the device.")
            debug(connected_reason)
            return False
        hmac_serial = config.hmac_serial(serial)
        files = config.IOS_DUMPFILES
        cmd = [
            os.path.join(config.SCRIPT_DIR, "ios_dump.sh"),
            hmac_serial,
            files["Apps"],
            files["Info"],
            files["Jailbroken-FS"],
            files["Jailbroken-SSH"],
        ]
        dumped = catch_err(run_command(cmd), " ".join(cmd)).strip()
        if dumped:
            debug("iOS DUMP RESULTS for {}:".format(hmac_serial))
            debug(dumped)
            return True
        else:
            debug(
                ">> The iOS dumping failed for some reason. Check above for more information"
            )
            return False

    def uninstall(self, serial, appid):
        validate_appid(appid)
        validate_serial(serial)
        # `--udid` targets the device that was scanned.
        ok, _ = run_checked(
            [f"{self.cli}ideviceinstaller", "--udid", serial, "--uninstall", appid]
        )
        return ok

    def isrooted(self, serial):
        # The jailbreak check is disabled until it is fixed. The old check, which
        # read the Jailbroken-FS and Jailbroken-SSH dumps, is in commit 66a0d56.
        return (False, "Jailbreak and root checks are currently disabled for iOS devices.")


class TestScan(AppScan):
    def __init__(self):
        super(TestScan, self).__init__("android", cli="cli")

    def get_apps(self, serialno):
        installed_apps = open(config.TEST_APP_LIST, "r").read().splitlines()
        return installed_apps

    def devices(self):
        return ["testdevice1", "testdevice2"]

    def get_system_apps(self, serialno, from_dump=False):
        return self.get_apps(serialno, from_dump)[:10]

    def get_offstore_apps(self, serialno, from_dump=False):
        return self.get_apps(serialno)[-4:]

    def uninstall(self, serial, appid):
        return True
