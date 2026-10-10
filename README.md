# Sherloc
### A.K.A. Software to Help with Evidence Retrieval and Log Online Cyberabuse

Sherloc is a tool to support computer security clinics. It is meant to be run by a tech clinic consultant, allowing the consultant to enter findings and investigations. Then, Sherloc enables the consultant to create an evidentiary document synthesizing the consultation.

Sherloc is built on [ISDI](https://github.com/stopipv/isdi), which checks Android or iOS devices for spyware.

## Installing Sherloc :computer:

Right now, Sherloc only natively supports **macOS and Linux**. If you are using a Windows device, you can use the Windows Subsystem for Linux 2
(WSL2), which can be installed by following [these instructions](https://docs.microsoft.com/en-us/windows/wsl/wsl2-install). After this, follow the remaining instructions as a Linux user would, cloning/running Sherloc inside the Linux container of your choice.

### Dependencies

These are written and tested for macOS users. We trust power (Linux) users know how to make the script work.

- Python 3.12 or newer (check your version with `python3 -V`)
- [adb](https://developer.android.com/studio/releases/platform-tools.html)
- expect
- ideviceinstaller
- wkhtmltopdf requirement
    - This project uses `wkhtmltopdf` to generate the evidentiary document. The brew cask for `wkhtmltopdf` is deprecated, so you will need to download the appropriate `wkhtmltopdf` binary from the project website: https://wkhtmltopdf.org/downloads.html.


#### Steps for macOS users

We rely on Homebrew to install packages on macOS.

Follow the steps in https://brew.sh/ to install the homebrew package manager.
Install the xcode developer tools if prompted as well.

(Something along the lines of `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`)

Then quickly install the project dependencies by running `brew bundle` in the sherloc subfolder.


##### Caveats
- wkhtmltopdf
    - If installing on Mac, this error will appear when opening the .pkg file "Apple could not verify “wkhtmltox-0.12.6-2.macos-cocoa.pkg” is free of malware that may harm your Mac or compromise your privacy.”
    To fix this go to System Settings > Privacy & Security > Security and see the message of the .pkg failing.
    Click open anyway and continue installation.

#### Debian family

```bash
sudo apt install adb expect libimobiledevice-utils ideviceinstaller ifuse
```

#### Windows Subsystem Linux (v2)
Installing **adb** is not so straightforward in WSL2, and
it won't work straightaway. You have to ensure having the *same* version of adb
*both* in WSL2 and in normal Windows (with `adb version`), then you will need to
start the adb process first in Windows, then in WSL2 (with for example `adb
devices`).

---

## Running Sherloc

After Sherloc is installed, run the following command in the terminal (in
the top-level directory of this repository):

```bash
cd sherloc
./sherloc.sh
```

There is an optional `--install` flag that installs requirements from `requirements.txt`. However, even without this flag, the script will notice if sherloc fails and install requirements anyway.

Sherloc is run in sudo by default, which is required to take screenshots on iPhones using `pymobiledevice3`. If you do not want to run Sherloc with sudo, please use the `--nosudo` flag when running `./sherloc`.

Sherloc should open `http://localhost:6200` in the browser.

Sherloc has no login and handles sensitive evidence, so it only listens on `127.0.0.1`. Requests whose `Host` header is not `localhost`, `127.0.0.1`, or `::1` are rejected. To serve it on another address, set `SHERLOC_HOST` (for example `0.0.0.0`) and list the host names clients will use in `SHERLOC_ALLOWED_HOSTS` (comma separated). Only do this on a network you trust.

### Requirements for taking screenshots with iOS devices

iOS devices have two requirements if you want to take screenshots.

1. Developer mode must be on (instructions below).
2. Sherloc must be run in `sudo`, which is the default when using `./sherloc.sh`.

To turn on developer mode:
1. Plug in the client’s phone.
2. Open XCode and start the OpenHaystack project.
3. Go to Product -> Destination -> Manage Run Destinations
4. Choose the client’s phone as the run location and hit Run. If it says Developer Mode must be opted into, hit cancel. Then enable Developer Mode on the phone in Settings > Privacy & Security > Developer Mode.
5. Restart the phone.

Please see this article for more details on how to turn on developer mode using XCode: https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device.

### Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md). `./dev.sh` sets up a development environment and runs the tests without root. Report security problems as described in [SECURITY.md](SECURITY.md).

### Debugging tips
If you encounter errors, please file a [GitHub issue](../../issues/) with the server error output.
Pull requests are welcome.

Sherloc prints no client data to the terminal (notes, names, device serials,
app lists), because terminal output outlives "Delete Client Data". Start it
with `DEBUG=1` to see that output while you debug, and clear it afterwards.

#### Cast iOS Screens or Mirror Android Screens
It is possible to view your
device screen(s) in real time on the macOS computer in a new window. This may
be useful to have while you are running the scan (and especially if you use the
privacy checkup feature), as it will be easy for you to see the mobile device
screen(s) in real time on the Mac side-by-side with the scanner.

**How to do it:**
You can mirror Android device screens in a new window using
[scrcpy](https://github.com/Genymobile/scrcpy), and cast iOS device screens on
macOS with QuickTime 10 (launch it and click File --> New Movie Recording -->
(on dropdown by red button) the iPhone/iPad name).

### Where client data is stored
All of it is under the `sherloc/` folder and is owner-only (folders `0700`,
files `0600`):

| Folder | Holds |
| --- | --- |
| `tmp-consult-data/` | only answers saved by an earlier version (JSON); they are moved into the database and removed on first use |
| `phone_dumps/` | phone dumps and their parsed copies |
| `webstatic/images/screenshots/` | screenshots |
| `reports/` | printouts and CSV reports |
| `data/` | the SQLite database (consultation answers, client notes, scans, app remarks) |

**Delete Client Data** on the evidence home page empties all of them and
overwrites the deleted database content. A notice at the top of every page
shows when any of this data is stored.

Sherloc does not encrypt this data. Run it on a computer with full-disk
encryption (FileVault, BitLocker or LUKS) and delete the data when the
consultation ends. Deleting overwrites the database content, but it cannot
promise that other copies are gone from a flash drive or a backup.

### The stalkerware app list
`sherloc/static_data/app-flags.csv` lists known stalkerware and dual-use apps.
A weekly GitHub workflow adds apps from
[AssoEchap/stalkerware-indicators](https://github.com/AssoEchap/stalkerware-indicators)
and opens a pull request; review and merge it to update the list. It only adds
apps. It never removes or edits a row. The app shows the source, the commit and
the date the list last changed on every page and in the full report.

### Take-home copy of the report
The evidence home page has a "Create take-home copy" button. The file it makes
leaves out the clinic's name and contact details, the client's name, device
serial numbers, the consultant's comments and screenshot metadata, and it is
named `notes-<random>.pdf`. You can set a password; tell it to the client in
person, not in the same message as the file. The file is not saved on the
computer. Sherloc cannot control what happens to the copy after the client
leaves, so talk through where it will be kept.

### Downloaded data
The data downloaded and stored in the study are the
following.  1. A `sqlite` database containing the feedback and actions taken by
the user.  2. `phone_dump/` folder will have dump of some services in the
phone.  (For Android I have figured out what are these, for iOS I don't know
how to get those information.)

#### Android
The services that we can dump safely using `dumpsys` are the
following.
* Application static details: `package` Sensor and configuration info:
* `location`, `media.camera`, `netpolicy`, `mount` Resource information:
* `cpuinfo`, `dbinfo`, `meminfo` Resource consumption: `procstats`,
* `batterystats`, `netstats`, `usagestats` App running information: `activity`,
* `appops`

See details about the services in [notes.md](notes.md)

#### iOS
Only the `appIds`, and their names. Also, I got "permissions" granted
to the application. I don't know how to get install date, resource usage, etc.
(Any help will be greatly welcomed.)
