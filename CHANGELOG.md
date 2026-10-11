# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Structure:
Added for new features.
Changed for changes in existing functionality.
Deprecated for soon-to-be removed features.
Removed for now removed features.
Fixed for any bug fixes.
Security in case of vulnerabilities.

## [Unreleased]

### Added
- Tests for the intake form (`tests/test_intake_form.py`). The test database fixture now also points Flask-SQLAlchemy at the temporary database; before, the ORM kept the engine it built at import, on the real `fieldstudy.db`
- `SHERLOC_DATA_DIR`: one folder for all client data (phone dumps, screenshots, reports, the consultation database) and the app log. Point it at a RAM disk and nothing about the client is written to the hard drive. Without it the folders stay where they were. `sherloc.sh` passes it (and `SHERLOC_HOST`, `SHERLOC_ALLOWED_HOSTS`) through `sudo`, which used to drop them. The app prints the folder at start. Screenshots are served by the app (`/client-screenshots/...`) so they can live outside `webstatic`
- A browser smoke test (`tests/test_browser_smoke.py`) clicks through the evidence home page in Chromium: report, take-home copy, and "Delete Client Data" with the confirmation accepted and cancelled. It fails on the nested-form bug fixed earlier. CI runs it in its own job
- The app shows where its stalkerware app list came from and when it last changed (a line on every page and in the full report). `scripts/get-stalkerware-indicators.py` records the source repository, the commit and its date, and the date of the change in `static_data/app-flags-source.json`; nothing is rewritten when there is nothing new. Until that file exists the app says the source and date are not recorded
- Take-home copy of the report ("Create take-home copy" on the evidence home page). It leaves out the clinic's name, logos and contact details, the client's name, device serial numbers, the consultant's comments and screenshot metadata. The file has a random neutral name and neutral PDF metadata, can be protected with a password (AES-256, `pypdf`), and is built in memory so no copy stays on the computer. The full report is unchanged
- `CONTRIBUTING.md`, `SECURITY.md` and a pull request template
- `./dev.sh` sets up a virtual environment and runs the tests without root; `requirements-dev.txt` lists the development tools
- Type annotations on `debuglog`, `inputcheck`, `clientdata` and `consultstore`, checked by mypy in the test suite (`tests/test_typed_modules.py`)

### Removed
- Flask-Migrate (and Alembic with it). There was no `migrations/` folder; `web/schema.sql` creates the tables. The note in `web/model/client.py` now says how to add a column. Flask-SQLAlchemy, which Sherloc imports directly, had only been installed as a dependency of Flask-Migrate; it is now pinned, and a test checks that every third-party import is pinned
- Dead and duplicate code. On main, ruff found 334 dead-code items: 75 unused imports, 20 unused variables and 236 lines of commented-out code. The lint ratchet now fails on any new one. Also removed:
  - Python: functions, classes and form classes nothing called; the always-empty `config.error()` plumbing; unreachable code (the disabled iOS jailbreak check is in git history, see the comment in `IosScan.isrooted`); a second copy of `run_capture` logic, now built on `runcmd.run_command`
  - Routes nothing in the app links to or calls: `/view_results` (a work-in-progress stub that redirected home), `/error`, `/saveapps/<scanid>` and `/savescan/<scanid>` (their only caller was a submit button that was commented out)
  - Templates never rendered (`evidence.html`, `summary.html`, `evidence-setup.html`); script tags outside any block in templates that extend a base, which Jinja never output, including jQuery 1.6.2 over plain HTTP; commented-out markup sent to the browser; uncalled JavaScript; an empty progress bar that nothing moved; a duplicate `<body>` tag
  - Files: `tests/config.py` (a stale copy of the config module), a byte-for-byte duplicate test file, a commented-out Flask tutorial test, broken helper scripts in `tests/` and `scripts/`, and unreferenced data in `static_data/`, including a 148 KB `ios-deploy` binary
- The `dataset` package. Only `data_process.py` used it, to open a database connection
- `filelock` from the requirements. No code uses it since the consultation answers moved to SQLite
- `pdfkit` and the `pip-audit` exception for its vulnerability

### Changed
- The PDF report is made with WeasyPrint instead of pdfkit and wkhtmltopdf. pdfkit has an unfixed vulnerability (CVE-2025-26240) and wkhtmltopdf is no longer maintained. WeasyPrint has no JavaScript engine, and the report may load only the app's own static files (`pdfrender.StaticOnlyFetcher`), read from disk instead of over HTTP. The page footer with page numbers now appears on every system (Linux builds of wkhtmltopdf ignored it). Page breaks and text size match the old report. Install Pango (`brew bundle`) instead of wkhtmltopdf. Supported Macs are Apple Silicon; Intel Macs are not supported. `printout_pdf_options` is replaced by `printout_footer` and `render_printout_pdf`
- Client IDs are four random words, such as `amber-otter-canyon-teapot`, drawn with `secrets` from a list of 2,951 everyday words (`clientwords.py`). The old IDs (`20261010_003`) showed the date and how many clients came before. The evidence workflow saved every scan under client ID `"1"`; it now uses the consultation's ID. "Delete client data" ends the consultation, so the next client gets a new ID
- The classic scan page no longer deletes an iPhone's device-info dump (`ios_info.xml`) right after a scan. It now matches the evidence workflow: the file stays with the rest of the client data, which "Delete client data" removes together (and which stays in memory in RAM-only mode)
- Both scan pages find the device and save the scan through one module, `scanflow.py` (issue #20). The evidence workflow's copy also built a page dictionary it never returned and had an iOS pairing branch that could not fail; both are gone. `config.DEVICE_PRIMARY_USER` was passed to four pages and read by none; it is removed
- The colour of an app row on the scan page is chosen by a template filter (`flag_class`) in the web layer. `blocklist.assign_class` and the scanner's `class_` column are gone
- Sherloc needs Python 3.12 or newer. Python 3.10 stopped receiving security fixes on 2026-10-01. CI runs the tests on 3.12 and, in a second job, on 3.13; `sherloc.sh`, the Brewfile, `dev.sh` and mypy use 3.12, and `main.py` refuses to start on an older Python. `tests/test_python_version.py` keeps these in step. The Dependabot rule that held back pandas 3 is removed, since pandas 3 needs 3.11
- CI fails when test coverage of `sherloc/` drops below 60% (it was 50%). Coverage is 75%
- The scan record, the root-check label and the suspicious/other app split are built in one place, `scanrecord.py`, for both the classic scan page and the evidence workflow. The root-check reason is now stored as plain text by both (the classic page stored it as JSON text)
- The indicator update script reads `ioc.yaml` with `yaml.safe_load` (it used `FullLoader`), adds an app listed twice only once, and the weekly pull request is titled "Update stalkerware indicators" (it was "[Example] Update stalkware indicators")
- `evidence_model.py` (1,135 lines) is split by domain into `evidence_base.py`, `evidence_accounts.py`, `evidence_apps.py` and `evidence_taq.py`; `evidence_model` re-exports every name. The scan routes moved from `web/view/evidence.py` to `web/view/evidence_scan.py`. The URLs are unchanged (`tests/test_routes_snapshot.py`)
- Four stale TODO/FIXME comments were removed or corrected. The rest are collected in issues #17 to #21
- Consultation answers (TAQ, scans, accounts, notes) are stored in the SQLite database, in the new `consult_documents` table, instead of four JSON files with lock files. One place to protect, count and wipe. JSON files from an earlier version are moved into the database the first time they are read, then overwritten and removed; an answer already in the database is never replaced by an old file, and a file that cannot be parsed is left alone. The `filelock` package is no longer used by the code
- The database tables are created from `schema.sql` on every start (it only uses `IF NOT EXISTS`), so a database from an earlier version gets the new table. Before, the schema ran only when the file did not exist
- Importing `config` no longer creates key files or folders. The keys are created on first use and the reports folder when the app starts. Scripts and tests that only read a setting no longer write into `static_data`
- Sherloc listens on 127.0.0.1 by default. Set `SHERLOC_HOST` and `SHERLOC_ALLOWED_HOSTS` to serve it elsewhere
- `pytest` runs from the repository root
- `config.ADB_PATH` is the plain path of `adb`, not a shell-quoted string
- Scanner tests run against fake `adb`, `pymobiledevice3` and `ideviceinstaller` programs (`tests/fakebin.py`), so they check the exact commands sent and the parsed results without a phone. Coverage of `sherloc/` rose from 41% to 52%, and CI fails below 50%. The canned tool output follows the documented formats; it is not recorded from a real device
- `evidence_collection.py` (1,900 lines) is split into `evidence_choices.py`, `evidence_model.py` and `evidence_forms.py`. It re-exports every name it had, so existing imports work, and `tests/test_evidence_collection_api.py` fails if one goes missing
- CI runs the test suite on pushes and pull requests. A lint ratchet (`tests/test_lint_ratchet.py`) fails on any new undefined name, invalid escape, mutable default argument, bare `except`, `shell=True` or `eval`; existing findings are recorded in `tests/lint_baseline.json`
- The stalkerware-indicators workflow uses the `sherloc/` paths and a single `token:` key (the duplicate key meant `IOC_UPDATE_KEY` was ignored), and its script exits non-zero when its requirements are missing. It no longer tries to open a PR on pull request runs
- super-linter checks changed files for serious Python problems and executable bits only; style linters were failing on the existing code
### Added
- Dependabot opens weekly updates for the GitHub Actions (their pinned hashes) and the Python packages
- A `pip-audit` workflow checks `sherloc/requirements.txt` on changes and every Monday. It ignores only the `pdfkit` advisory, with the reason next to it
- A notice at the top of every page shows when client data is stored on the computer, with a count for each kind
- `tests/test_client_data_leak.py` fills every place the app writes client data, deletes, and searches the whole tree for the text. `tests/test_data_write_sites.py` fails when code adds a new place that writes files or opens a database without it being listed and classified in `tests/data_write_sites.json`
### Fixed
- With Android Studio installed, Sherloc could not find adb. It used `$ANDROID_HOME/adb`, but the SDK keeps adb in `platform-tools/`. It now tries `platform-tools/adb`, then `$ANDROID_HOME/adb`, then `adb` on the PATH, and `SHERLOC_ADB` names it outright. `sherloc.sh` passes both settings through `sudo`
- A failed iOS dump was reported as a success: `catch_err` returned the error message, which counted as output. It now returns the output or "", and logs the error
- `phone_scanner/isdi_summarize.py` crashed on an intake form with no boxes ticked, printed a bound method instead of the device count unless the count was taken first, and shared its counts between summaries. Its answer labels now come from the same lists as the intake form (`intake_choices.py`) instead of a hand-kept copy
- The evidence pages loaded jQuery and Bootstrap from cdnjs, so without an internet connection they lost their layout and scripts, and the CDN could see when a consultation was running. Flask-Bootstrap now serves its own bundled copies (`BOOTSTRAP_SERVE_LOCAL`). A test checks that no page loads a script or stylesheet from another host
- The evidence workflow passed whatever serial number the device reported on to the scanner. It is now checked like on the classic scan page. The classic page's "scanning failed" message no longer points to a `report_failed.md` that does not exist
- The scan page's "Devices scanned for this client" listed every device ever scanned on the computer, with its model and owner, not only this client's. It now lists this client's devices, and nothing when there are none (it showed the heading with an empty link)
- Client IDs could repeat or carry the wrong date. `new_client_id` compared UTC timestamps with local midnight, so after midnight east of UTC the first IDs of the day were handed out again, and west of UTC the evening's clients counted for the next day. It now reads today's IDs themselves, counts clients who were scanned without an intake form, and skips IDs in other formats (it crashed on them)
- Intake forms are stamped in local time like the other tables. They used UTC, the "off by 4 hours" in the code. Forms saved before this change keep their UTC time
- The intake form (`/form/`) did not enforce its required questions (labels ending in `*`). Column defaults made `wtforms_alchemy` add `Optional()`, which ends validation on a blank answer before `InputRequired()` runs, so a form with no consultant names or FJC was saved. "Chief concerns" and "Vulnerabilities discovered" had no check at all. All are now required
- Editing a saved intake form with an invalid answer still wrote it to the database. It now shows the errors and keeps the saved form. Opening an old form whose checkbox answers were empty no longer crashes, and submitting edits without choosing a form goes back to the list instead of a 400 error
- "Delete Selected Screenshots" deleted whatever path the form sent. It now deletes only files inside the screenshot folder. Current browsers could not be made to send that request from another site (the `Sec-Fetch-Site` and `Origin` checks in `web/security.py` refuse it); a browser that sends neither header could
- The app log path was relative to the working directory (`../logs/app.log`) and failed if that folder did not exist. It is now `logs/` in the data folder, created when needed
- `phone_scanner/data_process.py`, the script that rebuilds the app list and app-info database from crawls, had stopped working: it read `config.SPYWARE_LIST_FILE`, which does not exist, and pandas no longer writes through the SQLAlchemy 1.4 engine it used. It now runs, writes the database through `sqlite3`, and has tests
- Investigation answers for apps added by hand were all overwritten with the answers for the last app: apps were matched by app id, and hand-added apps have none. Answers are now paired with apps by position
- The manual-add form could not be saved unless "Is the device rooted?" was answered; its default, "none", was not one of the choices, and the error read "Not a valid choice"
- The app selection page failed with an error for a scan that found no apps, and an unknown device serial in a scan URL gave a server error instead of "not found"
- After a failed validation on the app selection page, the redirect itself failed (`url_for` was missing the serial)
- Scanning "from dump" on the classic scan page never found the earlier scan: it looked the device up by the raw serial, while the database stores the pseudonymized one. With no earlier scan it carried on with an empty scan id instead of saying so
- Screenshots of the eleventh and later accounts were filed under the wrong account: only the last digit of the account number was read, so account 12's screenshots appeared in account 2's section of the report
- App details failed with `IndentationError` for the last package in an Android dump, and for any package followed by another section: the package's text ran on into the next section. It now ends at the next line indented no deeper than the package header
- Data usage from an old dump's `net_stats` compared the app uid as text with a numeric column, so it always showed 0.00 MB; with empty or unexpected `net_stats` it crashed. It now matches the uid as a number and answers "unknown" when it cannot tell. Current scans do not collect `net_stats`
- Scanning from a dump always showed the root check as `<ROOTED_ERR>`: `get_is_rooted` passed the serial as a string instead of a one-item tuple, so the query failed
- The indicator update glued its first new row onto the last row of `app-flags.csv`, which has no final newline, damaging both rows. It now starts a new line first. Pull request #4 on the fork was made by the old script and contains the damaged row
- The "Delete Client Data" button, and the Delete buttons for scans and accounts, on the evidence home page did nothing. Each was a form inside another form, which browsers drop, so a click saved the notes form instead and showed no confirmation. They now post to their own routes after a confirmation. `tests/test_no_nested_forms.py` fails on any template with a nested form
- A failed uninstall was reported as a success, and the app was recorded as deleted in the database even though it was still on the phone. `uninstall` now returns False when the tool exits non-zero, prints `Failure`/`ERROR`, is missing or times out
- A failed `adb` app listing was read as a list of apps (the error text). It now restarts the adb server and returns no apps
- Android device descriptions no longer keep the newline that `getprop` prints
- "Delete client data" stopped at the first missing folder (for example before any scan) and never reached the database. Each folder is now handled independently
- `python main.py test` did nothing: the call to `set_test_mode` discarded its result, and by then the paths had already been read. The `test` argument is now applied before `config` is imported
- A missing blocklist file made the app exit with status 0 and a one-line message. It now exits with an error
- 30 function arguments defaulted to a shared `list()`/`dict()`; each call now gets its own. Invalid escape sequences in 15 string literals are now raw strings (same values). A bare `except` in `/scan` is now `except ValueError`
- Android and iOS uninstall now target the scanned device (`adb -s`, `ideviceinstaller --udid`). Before, adb refused to run with more than one device attached. `delete_app` only accepts a serial that matches the scan
- iOS screenshots no longer break when the install path contains a space, and the `pymobiledevice3` tunnel process is stopped after each screenshot instead of being left running
- "Close App and End Session" never worked: it relied on `werkzeug.server.shutdown`, which Werkzeug 2.1+ removed. It now stops the app after sending its response
- `/view_results` raised a `NameError` for any existing scan. Removed unreachable or uncalled code that used undefined names (`index.py`, `android_permissions.py`, and `update_app_deleteinfo` in `db.py`, which also had an SQL typo). The lint check now fails on undefined names
### Security
- Every POST needs the session's CSRF token (Flask-WTF `CSRFProtect`). Cross-site requests were already refused by their `Sec-Fetch-Site` and `Origin` headers; the token also covers browsers that send neither. Forms carry it as a hidden field, and jQuery requests send it as the `X-CSRFToken` header. The token lasts for the browser session, so a form left open through a long consultation still submits. A refused request shows "Please reload the page"
- The client's name is no longer kept in the session cookie. Flask signs that cookie but does not encrypt it, and Sherloc kept it for a day, so the name sat readable in the browser profile. It is now stored with the consultation in the database and removed by "Delete client data"; a name left in an older cookie is dropped on the next request
- Every response is sent with `Cache-Control: no-store`, so browsers do not keep pages, screenshots or reports in their disk cache
- `filelock` is updated from 3.17.0 to 3.20.3, which fixes two symlink race conditions that let a local user truncate or interfere with files through lock files (GHSA-w853-jp5j-5j7f, GHSA-qmgc-5h2g-mvrw)
- The PDF printout turns JavaScript off in wkhtmltopdf. `pdfkit` 1.0.0 (CVE-2025-26240) lets page script run and read local files, and has no fixed release. User text was already escaped and local file access was already off
- Client notes, client names, device serials and app lists are no longer printed to the terminal. Terminal output outlives "Delete client data". Run with `DEBUG=1` to see it. Fixed messages such as "Uninstall failed" still print
- Folders that hold client data are created owner-only (`0700`), existing ones are tightened, and the app sets `umask 077`, so files made by the app or by the programs it starts are `0600`. An older database file is tightened at start. When Sherloc runs under `sudo`, those files belong to root
- Screenshots are saved in the folder that "Delete client data" empties (`config.SCREENSHOT_DIR`), not in a second hard-coded path
- No command runs through a shell any more. Every `adb`, `ideviceinstaller`, `pymobiledevice3` and script call is an argument list, so no value can be read as a command. `run_command` rejects a string. The package lookup (`sed` on the dump) and the pipes (`grep`, `sort`, `awk`, `tail`) are done in Python. The lint baseline is now empty
- App ids are validated before the package lookup and the recent-permissions lookup
- Request log lines show the route pattern instead of the URL, so device serials and app ids no longer appear in the terminal output
- Deleting client data, deleting a scan or account, and closing the app now require POST. A GET (an image tag, a link prefetch) could trigger them. The buttons are now forms
- App descriptions from the app-store crawls are reduced to a few formatting tags before rendering. They were inserted unescaped, so a published app could run script in the consultant's browser
- `/details/app` validates the app id and serial, and returns 404 for an unknown device
- App ids are passed to the delete-app handler as JSON, not pasted into a JavaScript string
- Deleting client data now also empties the database (client notes, scans and app remarks). Before, only files were deleted and the notes stayed in `fieldstudy.db`. Deleted content is overwritten and the file is compacted
- SQL statements are no longer echoed to the log (they included client notes and serials). Set `SHERLOC_SQL_ECHO=1` to turn echo back on for debugging
- Device serials and app ids are validated before they reach a shell command. Previously a crafted serial or app id, or a serial reported by a device, could run commands
- Fixed quoting in the Android and iOS uninstall commands that made `shlex.quote` ineffective
- Screenshot paths are limited to the screenshots directory
- Requests with a foreign `Host` header, a cross-origin `Origin` on state-changing methods, or a non-same-origin `Sec-Fetch-Site` are rejected, so another website cannot trigger scans, uninstalls, or data deletion
- `sherloc/static_data/pii.key` and `flask.secret` are no longer tracked by git and are ignored. Both files were public, so anyone could compute the `HSN_` device identifiers and forge session cookies. Keys are generated on first run with owner-only (0600) permissions, and a key file that still holds one of the previously published values is replaced. Existing installs get new keys after pulling, so stored `HSN_` identifiers will change. The old values remain in git history
- The PDF printout escapes notes, names and app text, and wkhtmltopdf no longer has local file access. Previously a note containing an `<iframe src="file://...">` tag put the contents of a local file into the report

## [v1.1.4] - November 4, 2025

### Added     
- "Open all dropdowns" buttons on TAQ and account check page
### Changed
- Only show relevant screenshot buttons on account check page
- Changed readme to account for Mac installation
- Account nickname changed to required username
- Changed names of consultation action buttons on homepage
### Deprecated
### Removed
### Fixed
- Patched issue with missing data and screenshot folders by adding during setup if needed
### Security

## [v1.1.3] - August 22, 2025

### Added     
### Changed
- Updated how screenshots show up on the printout for accounts and root
- Delete reports, too, when deleting client data
### Deprecated
### Removed
### Fixed
- Patched issue where some iPhones trigger duplicate column error during scan
- Patched issue where screenshots for apps are not separated by device
- Fix typo in the explanation of a successful root check
- Patched issue where Android scans try to access a folder that doesn't exist
### Security

## [v1.1.2] - August 14, 2025

### Added     
- Added LiveScreen (wifi.manager) to list of known spyware
### Changed
- Changed question about 2-factor (Issue 63)
- Changed wording of custody question (Issue 64)
- Moved client name input to homepage (Issue 66)
- Trimmed screenshot metadata in printout (Issue 65)
- Removed permissions from printout (Issue 69)
- Changed how root check is described by specifying what was checked.
### Deprecated
### Removed
### Fixed
### Security

## [v1.1.1] - August 8, 2025

### Added     
- Added instructions for installing `wkhtmltopdf` in `README`
- Added `exiftool` to `Brewfile` and `README` instructions
- Added back images that were deleted but we need for the UI

### Changed
- Updated .gitignore
- Updated printout to not show jailbreak part for iOS

### Deprecated
### Removed
### Fixed
- Fixed issue with EvidenceDataEncoder trying to encode Path objects
- Fixed issue with overwriting screenshots
### Security


## [v1.1.0] - August 5, 2025

### Added     

### Changed
- Major restructuring: Moved all Sherloc code into the `sherloc` folder.
- `isdi` file now renamed `main.py`.
- Created `./sherloc.sh` run script, which creates and activates a virtual environment, installs requirements if needed, and runs Sherloc in sudo (via `main.py`).
- Updated `README`.
- Resumed using this changelog.

### Deprecated
### Removed
- Unused files and folders, mostly .pngs in `webstatic/images`.
- Removed `libimobiledevice` from `Brewfile`. 

### Fixed
### Security
