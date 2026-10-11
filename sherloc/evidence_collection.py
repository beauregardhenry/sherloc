"""
Author: Sophie Stephenson
Date: 2023-03-15

Collect evidence of IPS. Basic version collects this data from the phone:

1. All apps that might be dual-use or spyware and data about them (install
    time, desc, etc.)
2. Permission usage in the last 7 days (or 28 days, if we can)

The consultation data classes live in `evidence_model`, the forms in
`evidence_forms` and the choice lists in `evidence_choices`. They are
re-exported here, so `evidence_collection.<name>` keeps working.
"""
import json
import os
import shutil
import sqlite3
from enum import Enum

import config
import consultstore
import jinja2
import pdfkit
from config import DUMP_DIR, REPORT_DIR, SCREENSHOT_DIR, SHERLOC_VERSION, screenshot_path
import scanflow
from scanrecord import split_suspicious
from web.view.index import get_device

from evidence_choices import (  # noqa: F401
    TMP_CONSULT_DATA_DIR,
    YES_NO_DEFAULT,
    PERSON_DEFAULT,
    LEGAL_DEFAULT,
    TWO_FACTOR_DEFAULT,
    SECOND_FACTORS,
    ACCOUNTS,
    EMPTY_CHOICE,
    YES_NO_UNSURE_CHOICES,
    YES_NO_CHOICES,
    PERSON_CHOICES,
    PWD_CHOICES,
    LEGAL_CHOICES,
    DEVICE_TYPE_CHOICES,
    TWO_FACTOR_CHOICES,
)
from evidence_model import (  # noqa: F401
    EvidenceDataEncoder,
    Dictable,
    DictInitClass,
    AccountSection,
    SuspiciousLogins,
    PasswordCheck,
    RecoverySettings,
    TwoFactorSettings,
    SecurityQuestions,
    InstallInfo,
    PermissionInfo,
    AppInfo,
    Risk,
    RiskReport,
    TAQDevices,
    TAQAccounts,
    TAQSharing,
    TAQSmarthome,
    TAQKids,
    TAQLegal,
    Notes,
    ConsultationData,
    AccountInvestigation,
    ScanData,
    TAQData,
    ConsultSetupData,
    ConsultNotesData,
    ScreenshotInfo,
    get_all_screenshot_files,
)
from debuglog import debug
from evidence_forms import (  # noqa: F401
    NotesForm,
    PermissionForm,
    InstallForm,
    SuspiciousLoginsForm,
    PasswordForm,
    RecoveryForm,
    TwoFactorForm,
    SecurityQForm,
    AppSelectForm,
    StartForm,
    SingleAppCheckForm,
    AppInvestigationForm,
    AccountCompromiseForm,
    AppSelectPageForm,
    ManualAppSelectForm,
    ManualAddPageForm,
    ScreenshotEditForm,
    MultScreenshotEditForm,
    TAQDeviceCompForm,
    TAQAccountsForm,
    TAQSharingForm,
    TAQSmartHomeForm,
    TAQKidsForm,
    TAQLegalForm,
    TAQForm,
    HomepageNoteForm,
)


def get_scan_by_ser(ser, all_scan_data: list[ScanData]):

    for scan in all_scan_data:
        if scan.serial == ser:
            return scan

    return ScanData()


def update_scan_by_ser(new_scan: ScanData, all_scan_data: list[ScanData]):
    """
    Adds new_scan to all_scan_data.
    If new_scan matches serial numbers of an existing scan, it replaces that scan.
    Otherwise, it appends the new scan to the list.
    """

    for i in range(len(all_scan_data)):
        scan = all_scan_data[i]

        # if serial numbers match, replace with the new one
        if scan.serial == new_scan.serial:
            all_scan_data[i] = new_scan
            return all_scan_data

    # Otherwise, just append the new scan
    all_scan_data.append(new_scan)
    return all_scan_data

class ConsultDataTypes(Enum):
    TAQ = 1
    SCANS = 2
    ACCOUNTS = 3
    NOTES = 4

def get_data_filename(datatype: ConsultDataTypes):

    if datatype == ConsultDataTypes.TAQ.value:
        return "taq.json"
    elif datatype == ConsultDataTypes.SCANS.value:
        return "scans.json"
    elif datatype == ConsultDataTypes.ACCOUNTS.value:
        return "accounts.json"
    else:
        return "notes.json"


def render_printout_html(context):
    """Render the printout template to an HTML string."""
    template_loader = jinja2.FileSystemLoader("./")
    # Notes, nicknames and app names are free text and wkhtmltopdf renders the
    # result, so everything is HTML-escaped.
    template_env = jinja2.Environment(loader=template_loader, autoescape=True)
    template_env.filters["screenshot_path"] = screenshot_path
    template = template_env.get_template(os.path.join('templates', 'printout.html'))
    return template.render(context)


def printout_pdf_options(takehome=False):
    # No 'enable-local-file-access': the page is built from user-entered text, and
    # images are fetched from the running app over http (see url_root).
    # JavaScript is off: pdfkit 1.0.0 (CVE-2025-26240) lets page script run
    # and read local files, and the printout needs none.
    opts = {
        'disable-javascript': '',
        'margin-top': '15mm',
        'margin-bottom': '20mm',
        'margin-left': '10mm',
        'margin-right': '10mm',
        'footer-spacing': '5',
        'footer-center': 'Created by Madison Tech Clinic using Sherloc {} • Page [page] of [toPage]'.format(SHERLOC_VERSION),
        'footer-font-name': 'Georgia',
        'footer-font-size': '8',
    }
    if takehome:
        # Nothing that names the clinic or the tool. The file's own metadata is
        # replaced in takehome.protect_pdf.
        opts['footer-center'] = 'Page [page] of [toPage]'
    return opts


def create_printout(context, out_file=None):
    out_file = out_file or os.path.join(REPORT_DIR, 'test_report.pdf')
    css_path = os.path.join('webstatic', 'style.css')

    html_string = render_printout_html(context)

    wkhtmltopdf = shutil.which('wkhtmltopdf') or '/usr/local/bin/wkhtmltopdf'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf)

    pdfkit.from_string(html_string, out_file, options=printout_pdf_options(), configuration=config, css=css_path, verbose=True)

    debug("Printout created. Filename is", out_file)

    return out_file


def remove_unwanted_data(data):
    """Clean data from forms (e.g., remove CSRF tokens so they don't live in the session)"""
    unwanted_keys = ["csrf_token"]

    if isinstance(data, list):
        return [remove_unwanted_data(d) for d in data]

    elif isinstance(data, dict):
        new_data = {}
        for k in data.keys():
            if k not in unwanted_keys:
                new_v = remove_unwanted_data(data[k])
                new_data[k] = new_v

        return new_data

    else:
        return data


def get_multiple_app_details(device, ser, apps):
    filled_in_apps = []
    for app in apps:
        d = get_app_details(device, ser, app["id"])
        d["flags"] = app["flags"]
        d["appId"] = app["id"]
        filled_in_apps.append(d)
    return filled_in_apps

def get_app_details(device, ser, appid):
    sc = get_device(device)
    d, info = sc.app_details(ser, appid)

    # Copy some info over from the info dict
    # TODO: Just return this all in one clean dictionary from app_details()...
    info_things = ["install_time", "last_updated", "app_version"]
    for item in info_things:
        try:
            d[item] = info[item]
            if d[item].strip() == "":
                d[item] = ""
        except KeyError:
            d[item] = ""


    return d

def get_scan_obj(device, nickname):
    """Create the scan object."""
    sc = get_device(device)
    if not sc:
        raise Exception("Please choose one device to scan.")
    if not nickname:
        raise Exception("Please give the device a nickname.")
    return sc

def get_ser_from_scan_obj(sc):
    """The serial of the connected device. Raises `scanflow.ScanFailed`."""
    return scanflow.find_serial(sc)

def get_serial(device, nickname):
    sc = get_scan_obj(device, nickname)
    ser = get_ser_from_scan_obj(sc)
    return ser


def get_scan_data(device, device_owner):
    """Scan the device for the evidence workflow. Raises `scanflow.ScanFailed`."""
    sc = get_scan_obj(device, device_owner)
    ser = get_ser_from_scan_obj(sc)
    debug(">>>scanning_device", device, ser, "<<<<<")

    result = scanflow.run_device_scan(
        sc,
        device=device,
        ser=ser,
        device_owner=device_owner,
        clientid="1",
        include_raw_serial=True,
    )
    suspicious_apps, other_apps = split_suspicious(result.apps)
    detailed_suspicious_apps = get_multiple_app_details(device, ser, suspicious_apps)
    detailed_other_apps = get_multiple_app_details(device, ser, other_apps)
    return result.scan, detailed_suspicious_apps, detailed_other_apps


def _store_name(datatype):
    return get_data_filename(datatype)[: -len(".json")]


# Save the consultation answers in the database.
# Overwrites them always, assume any previous data has been incorporated
def save_data_as_json(data, datatype: ConsultDataTypes):
    json_object = json.dumps(data, cls=EvidenceDataEncoder)
    consultstore.save(_store_name(datatype), json_object, TMP_CONSULT_DATA_DIR)


def load_json_data(datatype: ConsultDataTypes):
    body = consultstore.load(_store_name(datatype), TMP_CONSULT_DATA_DIR)
    if body is None:
        if datatype in [ConsultDataTypes.NOTES.value, ConsultDataTypes.TAQ.value]:
            return dict()
        return list()
    return json.loads(body)

def load_object_from_json(datatype: ConsultDataTypes):
    json_data = load_json_data(datatype)
    if datatype == ConsultDataTypes.TAQ.value:
        return TAQData(**json_data)

    if datatype == ConsultDataTypes.ACCOUNTS.value:
        assert isinstance(json_data, list)
        return [AccountInvestigation(**acct) for acct in json_data]

    if datatype == ConsultDataTypes.SCANS.value:
        assert isinstance(json_data, list)
        return [ScanData(**scan) for scan in json_data]

    if datatype == ConsultDataTypes.NOTES.value:
        return ConsultNotesData(**json_data)

    return None

def wipe_client_database():
    """Remove every row of client data from the SQLite database.

    The schema stays so the app keeps working. Deleted content is overwritten
    (secure_delete) and the file is rewritten (VACUUM), so it cannot be
    recovered from free pages. Does nothing when the database does not exist.
    """
    path = config.SQL_DB_PATH.replace("sqlite:///", "", 1)
    if not os.path.exists(path):
        return

    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA secure_delete = ON")
        tables = [
            r[0]
            for r in con.execute(
                "select name from sqlite_master where type = 'table' "
                "and name not like 'sqlite_%' and name != 'alembic_version'"
            )
        ]
        with con:
            for table in tables:
                con.execute('delete from "{}"'.format(table.replace('"', '""')))
            if con.execute(
                "select 1 from sqlite_master where name = 'sqlite_sequence'"
            ).fetchone():
                con.execute("delete from sqlite_sequence")
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("VACUUM")
    finally:
        con.close()


def delete_client_data():

    # Answers from an earlier version that are still stored as json files.
    # The ones in the database are removed with the rest of it, below.
    debug("Deleting consultation data...")
    consultstore.discard_legacy_files(TMP_CONSULT_DATA_DIR)

    # Delete phone dumps
    debug("Deleting phone dumps...")
    debug(DUMP_DIR)
    shutil.rmtree(DUMP_DIR, ignore_errors=True)
    os.makedirs(DUMP_DIR, mode=0o700, exist_ok=True)

    # Delete screenshots
    debug("Deleting screenshots...")
    debug(SCREENSHOT_DIR)
    shutil.rmtree(SCREENSHOT_DIR, ignore_errors=True)
    os.makedirs(SCREENSHOT_DIR, mode=0o700, exist_ok=True)

    # Delete report
    debug("Deleting report...")
    debug(REPORT_DIR)
    shutil.rmtree(REPORT_DIR, ignore_errors=True)
    os.makedirs(REPORT_DIR, mode=0o700, exist_ok=True)

    # Delete everything stored in the database
    debug("Deleting database records...")
    wipe_client_database()

    debug("Client data deleted.")
