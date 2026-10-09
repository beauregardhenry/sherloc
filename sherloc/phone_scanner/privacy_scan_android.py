"""
Author: Rahul Chatterjee
Date: 2018-06-11
Doc: https://docs.google.com/document/d/1HAzmB1IiViMrY7eyEt2K7-IwqFOKcczsgtRRaySCInA/edit

Privacy configuration for Android. An attempt to automate most of this.


Automatic settings check

To find what activity is running on the current window (*Super useful command*)

    adb shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'

Finally screen capture.

    adb shell screencap -p | perl -pe 's/\x0D\x0A/\x0A/g' > screen.png


1. Check the Accounts & Sync
    adb shell am start 'com.android.settings/.Settings\\$AccountsGroupSettingsActivity'
2. Check the Google Account settings
    adb shell am start 'com.google.android.gms/com.google.android.gms.app.settings.GoogleSettingsLink'
3. Backup and reset
    adb shell am start 'com.android.settings/.Settings\\$PrivacySettingsActivity'
4. Check location sharing settings
    adb shell am start 'com.google.android.apps.maps/com.google.android.maps.MapsActivity' && sleep 5 && adb shell input tap 20 80
5. Check photo sharing settings
    adb shell am start 'com.google.android.apps.photos/com.google.android.apps.photos.home.HomeActivity' && sleep 10 && adb shell input tap 20 80
"""

import os
import random
import re
import shlex
import subprocess
import time
from datetime import datetime
from subprocess import PIPE, Popen, TimeoutExpired

from flask import url_for

import config
from inputcheck import validate_serial

# Activity names look like `com.example/.Settings\$Inner`. The backslash is for
# the shell on the device, which turns `\$` into `$`. Names come from this
# file, but they are checked anyway because the device shell will read them.
_ACTIVITY = re.compile(r"[A-Za-z0-9_./\\$]+")


def run_capture(args, timeout=4):
    """Run a program and return (stdout, stderr) as text.

    `args` is a list; no shell is involved. Not the same as
    `runcmd.run_command`, which returns the process.
    """
    print(" ".join(shlex.quote(a) for a in args))
    try:
        p = Popen(args, stdout=PIPE, stderr=PIPE)
        p.wait(timeout)
        return p.stdout.read().decode("utf-8"), p.stderr.read().decode("utf-8")
    except FileNotFoundError as e:
        return "", f"Command not found: {e}"
    except TimeoutExpired:
        p.kill()
        return "", "Command timed out"
    except Exception as e:
        return "", f"Error: {e}"


def thiscli(ser):
    """Return the adb command as a list. `None` means the default device."""
    if ser is None:
        return [config.ADB_PATH]
    return [config.ADB_PATH, "-s", validate_serial(ser)]


def get_screen_res(ser):
    out, err = run_capture(thiscli(ser) + ["shell", "dumpsys", "window"])
    for line in out.splitlines():
        if "mUnrestrictedScreen" in line:
            m = re.match(r"mUnrestrictedScreen=\(0,0\) (?P<w>\d+)x(?P<h>\d+)", line.strip())
            if m:
                return int(m.group("w")), int(m.group("h"))
            break
    return -1, -1


def open_activity(ser, activity_name):
    """
    Opens an activity
    """
    if not _ACTIVITY.fullmatch(activity_name):
        raise ValueError("Unsupported activity name.")
    out, err = run_capture(thiscli(ser) + ["shell", "am", "start", activity_name])
    if err:
        print("ERROR (open_activity): {!r}".format(err))
        return False
    if "error" in out.lower():
        print("ERROR (open_activity) stdout=: {!r}".format(out))
        return False
    return True


def tap(ser, xpercent, ypercent):
    """
    Tap at xpercent and ypercent from top left
    """
    w, h = get_screen_res(ser)
    x = int(xpercent * w / 100)
    y = int(ypercent * h / 100)
    out, err = run_capture(thiscli(ser) + ["shell", "input", "tap", str(x), str(y)])
    if err:
        print("ERROR (tap): {!r}".format(err))


def keycode(ser, evt):
    cmds = {"home": "3", "back": "4", "menu": "82", "power": "26"}
    if evt not in cmds:
        print("ERROR (keycode): No support for {}".format(evt))

    key = cmds.get(evt)
    run_capture(thiscli(ser) + ["shell", "input", "keyevent", str(key)])


def is_screen_on(ser):
    out, err = run_capture(thiscli(ser) + ["shell", "dumpsys", "input_method"])
    if err:
        print("ERROR (is_screen_on): {!r}".format(err))
    states = [
        re.sub(r".*mInteractive=", "", line).strip()
        for line in out.splitlines()
        if "mInteractive" in line
    ]
    return bool(states) and states[0] == "true"


def take_screenshot(ser, fname=None):
    """
    Take a screenshot and output the iamge
    """
    # if not is_screen_on(ser):
    #     keycode(ser, 'power'); keycode(ser, 'menu') # Wakes the screen up
    if not fname:
        fname = "tmp_screencap.png"

    cmd = thiscli(ser) + ["exec-out", "screencap", "-p"]

    try:
        # This command spits out the screenshot to stdout, which we capture
        # and write to the file.
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
        data = result.stdout
        if os.name != "posix":
            data = data.replace(b"\r\n", b"\n")  # Windows adb translates line ends
        with open(fname, 'wb') as f:
            f.write(data)

        # Return the image that will be inserted into the HTML.
        return add_image(fname.split("webstatic/", 1)[-1], nocache=True)

    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}: {e.output}")
        return "<div class='screenshotfail'>Screenshot failed with exit code {}</div>".format(e.returncode)

    except Exception as e:
        print(e)
        return "<div class='screenshotfail'>Screenshot failed with exception {}</div>".format(e)


def wait(t):
    time.sleep(t)

def add_image(img, nocache=False):
    #rand = random.randint(0, 10000)
    return (
        "<img height='400px' src='"
        + url_for("static", filename=img)
        + "'/>"
    )

def do_privacy_check(ser, command, context):

    command = command.lower()
    if command == "account":  # 1. Account ownership  & 3. Sync (if present)
        open_activity(
            ser,
            "com.google.android.gms/com.google.android.gms.app.settings.GoogleSettingsLink",
        )
        # wait(2)
        # keycode(ser, 'home')
        # take_screenshot(ser, 'account.png')
        return (
            "Click on the <code>Google Account</code> on the phone, and check the "
            "<em>account email address</em> at the top."
        )
    elif command == "backup":  # 2. Backup & reset
        open_activity(ser, r"com.android.settings/.Settings\$PrivacySettingsActivity")
        # wait(2)
        # keycode(ser, 'home')
        # take_screenshot(ser, 'account.png')
        return (
            "If backup is <b>on</b>, then check the email address where <code>Backup "
            "account</code> is registered to."
        )
    elif command == "gmap":  # 4. Google Maps sharing
        open_activity(
            ser, "com.google.android.apps.maps/com.google.android.maps.MapsActivity"
        )
        wait(2)
        keycode(ser, "menu")
        return "Check the <code>location sharing</code> option; " + add_image(
            "google_maps_sharing.png"
        )
    elif command == "gphotos":  # 5. Google Photos sharing
        open_activity(
            ser,
            "com.google.android.apps.photos/com.google.android.apps.photos.home.HomeActivity",
        )
        wait(2)
        keycode(ser, "menu")
        return "Check the <code>Shared library</code>. " + add_image(
            "google_maps_sharing.png"
        )
    elif command == "sync":
        if not open_activity(
            ser, r"com.android.settings/.Settings\$AccountsGroupSettingsActivity"
        ):
            return (
                "I could not find syncing functionality in your Android. This most likely mean this is not available, "
                "and no need to check."
            )
        else:
            return (
                "Click on the <code>Google</code> (or other account) where the phone is syncing its data "
                "and what data is being synced."
            )

    elif command == "screenshot":
        fname = config.create_screenshot_fname(context, ser)
        return take_screenshot(ser, fname=fname)

    else:
        return "Command not supported; should be one of ['account', 'backup', 'gmap', 'gphotos'] (case in-sensitive)"


if __name__ == "__main__":
    # ser = "ZY224F8TKG"
    # print(get_screen_res(ser)
    # print(is_screen_on(ser))
    # do_privacy_check(ser, 'account')
    take_screenshot(ser=None)
