import io
import json
import os
import time
from datetime import datetime

import config
from evidence_collection import (
    TMP_CONSULT_DATA_DIR,
    DEVICE_TYPE_CHOICES,
    LEGAL_CHOICES,
    PERSON_CHOICES,
    PWD_CHOICES,
    TWO_FACTOR_CHOICES,
    YES_NO_UNSURE_CHOICES,
    AccountCompromiseForm,
    AccountInvestigation,
    ConsultationData,
    ConsultDataTypes,
    ConsultNotesData,
    HomepageNoteForm,
    MultScreenshotEditForm,
    TAQData,
    TAQForm,
    create_printout,
    delete_client_data,
    get_scan_by_ser,
    get_ser_from_scan_obj,
    load_json_data,
    load_object_from_json,
    save_data_as_json,
)
from flask import (
    flash,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_bootstrap import Bootstrap
from phone_scanner import AndroidScan, IosScan
import consultstore
import indicators
from takehome import create_takehome_pdf, neutral_filename
from web import app
from debuglog import debug, pdebug

bootstrap = Bootstrap(app)

USE_PICKLE_FOR_SUMMARY = False
USE_FAKE_DATA = True


@app.route("/evidence/home", methods={'GET', 'POST'})
def evidence_home():

    notes = load_json_data(ConsultDataTypes.NOTES.value)
    pdebug(notes)

    consult_data = ConsultationData(
        taq=load_json_data(ConsultDataTypes.TAQ.value),
        accounts=load_json_data(ConsultDataTypes.ACCOUNTS.value),
        scans=load_json_data(ConsultDataTypes.SCANS.value),
        screenshot_dir = config.SCREENSHOT_DIR,
        notes = load_json_data(ConsultDataTypes.NOTES.value)
    )

    form = HomepageNoteForm(**consult_data.notes.to_dict())

    context = dict(
        task = "evidence-home",
        title=config.TITLE,
        consultdata=consult_data.to_dict(),
        form = form
    )

    if request.method == 'GET':

        return render_template('main.html', **context)

    if request.method == 'POST':

        pdebug(form.data)

        if form.is_submitted() and form.validate():

            if form.generate_printout.data:
                client = form.data["client_name"]
                if not client:
                    flash("Client name not entered. Please provide a name to put in the report.")
                    return redirect(url_for('evidence_home'))

                # Kept in the database, not the session cookie: the cookie is
                # signed but readable, and lives in the browser profile.
                save_report_client(client)
                return redirect(url_for('evidence_printout'))

            if form.submit:
                new_notes = ConsultNotesData(**form.data)
                save_data_as_json(new_notes, ConsultDataTypes.NOTES.value)

                return redirect(url_for('evidence_home'))

        elif not form.validate():
            flash("Form validation error. Raw error: {}".format(form.errors), 'error')
            return render_template('main.html', **context)


@app.route("/evidence/taq", methods={'GET', 'POST'})
def evidence_taq():

    form = TAQForm()

    # Load the form including any existing data
    if request.method == 'GET':

        # Load any data we already have
        taq_data = load_object_from_json(ConsultDataTypes.TAQ.value)

        form.process(data=taq_data.to_dict())

        context = dict(
            task = "evidence-taq",
            form = form,
            title=config.TITLE,
            sessiondata = taq_data.to_dict()
        )

        return render_template('main.html', **context)


    # Submit the form
    if request.method == 'POST':

        if form.is_submitted() and form.validate():

            # load data as class
            taq_data = TAQData(**form.data)

            # save clean data
            save_data_as_json(taq_data, ConsultDataTypes.TAQ.value)

            return redirect(url_for('evidence_home'))

        elif not form.validate():
            flash("Form validation error. Raw error: {}".format(form.errors), 'error')
            return redirect(url_for('evidence_taq'))

    return redirect(url_for('evidence_taq'))



@app.route("/evidence/account", methods={'GET'})
def evidence_account_default():

    # consider adding a place to save the num scans later if it becomes a pain to load it
    accounts = load_object_from_json(ConsultDataTypes.ACCOUNTS.value)
    if isinstance(accounts, list):
        new_id = len(accounts)
    else:
        new_id = 0

    return redirect(url_for('evidence_account', id=new_id))

@app.route("/evidence/account/<int:id>", methods={'GET', 'POST'})
def evidence_account(id):

    all_account_data = load_object_from_json(ConsultDataTypes.ACCOUNTS.value)
    current_account = AccountInvestigation(account_id=id)

    if len(all_account_data) > id:
        current_account = all_account_data[id]

    # This is so that we can take screenshots if needed
    ios_ser = None
    android_ser = None

    try:
        ios_scan_obj = IosScan()
        ios_ser = get_ser_from_scan_obj(ios_scan_obj)
    except:  # noqa
        pass

    try:
        android_scan_obj = AndroidScan()
        android_ser = get_ser_from_scan_obj(android_scan_obj)
    except:  # noqa
        pass

    form = AccountCompromiseForm()

    if request.method == 'GET':
        form.process(data=current_account.to_dict())

        context = dict(
            task = "evidence-account",
            form = form,
            title=config.TITLE,
            android_ser = android_ser,
            ios_ser = ios_ser,
            sessiondata = current_account.to_dict()
            # for now, don't load anything
        )

        return render_template('main.html', **context)

    # Submit the form if it's a POST
    if request.method == 'POST':
        if form.is_submitted() and form.validate():

            # save data in class
            account_investigation = AccountInvestigation(**form.data, account_id=id)

            # add it to the account data
            if len(all_account_data) <= id:
                all_account_data.append(account_investigation)
            else:
                all_account_data[id] = account_investigation

            save_data_as_json(all_account_data, ConsultDataTypes.ACCOUNTS.value)

            return redirect(url_for('evidence_home'))

        if not form.validate():
            flash("Form validation error. Raw error: {}".format(form.errors), 'error')
            pdebug(form.errors)

app.add_template_filter(config.screenshot_path, "screenshot_path")


@app.route("/client-screenshots/<path:relpath>")
def client_screenshot(relpath):
    return send_from_directory(config.SCREENSHOT_DIR, relpath)


@app.route("/evidence/screenshots", methods=['GET', 'POST'])
def evidence_screenshots():

    pdebug("Gathering consult data...")
    consult_data = ConsultationData(
        accounts=load_json_data(ConsultDataTypes.ACCOUNTS.value),
        scans=load_json_data(ConsultDataTypes.SCANS.value),
        screenshot_dir = config.SCREENSHOT_DIR,
    )

    pdebug("Gathering screenshots...")
    consult_data.prepare_screenshots(get_metadata=False)

    pdebug("Reformatting screenshot info...")
    root_screenshots = list()
    app_screenshots = list()
    acct_screenshots = list()

    for scan in consult_data.scans:
        root_screenshots.extend(scan.screenshot_info)
        for a in scan.selected_apps:
            app_screenshots.extend(a.screenshot_info)

    for account in consult_data.accounts:
        for section in [account.suspicious_logins,
                        account.recovery_settings,
                        account.two_factor_settings,
                        account.security_questions]:
            acct_screenshots.extend(section.screenshot_info)

    form = MultScreenshotEditForm(root_screenshots=root_screenshots,
                                  app_screenshots=app_screenshots,
                                  acct_screenshots=acct_screenshots)

    url_root = request.url_root

    if request.method == 'GET':

        context = dict(
            task = "evidence-screenshots",
            title=config.TITLE,
            rooted_screenshot_info = root_screenshots,
            app_screenshot_info = app_screenshots,
            account_screenshot_info = acct_screenshots,
            form = form,
            url_root = url_root
        )

        return render_template('main.html', **context)

    if request.method == 'POST' and form.is_submitted():
        # Delete all screenshots that were selected for deletion
        for a in form.data["app_screenshots"] + form.data["acct_screenshots"] + form.data["root_screenshots"]:
            path = config.inside_screenshot_dir(a["fname"]) if a["delete"] else None
            if path and os.path.isfile(path):
                os.remove(path)

        # Reload the screenshot page
        return redirect(url_for('evidence_screenshots'))

def save_report_client(name):
    """Remember the name for the report until client data is deleted."""
    consultstore.save("report_client", json.dumps(name), TMP_CONSULT_DATA_DIR)


def load_report_client():
    body = consultstore.load("report_client", TMP_CONSULT_DATA_DIR)
    return json.loads(body) if body else ""


def _printout_context(client):
    """Everything the printout template needs, for the current consultation."""
    pdebug("Gathering consult data...")
    consult_data = ConsultationData(
        setup=dict(
            client=client,
            date=datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        ),
        taq=load_json_data(ConsultDataTypes.TAQ.value),
        accounts=load_json_data(ConsultDataTypes.ACCOUNTS.value),
        scans=load_json_data(ConsultDataTypes.SCANS.value),
        screenshot_dir = config.SCREENSHOT_DIR,
        notes=load_json_data(ConsultDataTypes.NOTES.value)
    )

    pdebug("Preparing reports...")
    consult_data.prepare_reports()

    pdebug("Gathering screenshots...")
    consult_data.prepare_screenshots()

    context = consult_data.to_dict()

    # Need url_root to load screenshots
    context["url_root"] = request.url_root

    # Which version of the stalkerware app list the apps were checked against
    context["indicator_list"] = indicators.describe(indicators.summary())

    # Need Sherloc version to print on the cover
    context["sherloc_version"] = config.SHERLOC_VERSION

    # Enable quick access of the text that maps to the saved Select responses
    context["select_text"] = dict()
    for question_tups in [YES_NO_UNSURE_CHOICES,
                          PERSON_CHOICES,
                          PWD_CHOICES,
                          LEGAL_CHOICES,
                          DEVICE_TYPE_CHOICES,
                          TWO_FACTOR_CHOICES]:
        for abbrv, full_text in question_tups:
            if abbrv.strip() != "":
                context["select_text"][abbrv] = full_text

    return context


@app.route("/evidence/printout/", methods=["GET"])
def evidence_printout():

    client = load_report_client()
    if not client:
        flash("Client name not entered. Please provide a name to put in the report.")
        return redirect(url_for("evidence_home"))

    start_time = time.perf_counter()
    context = _printout_context(client)

    # create the printout document

    pdebug("Creating the printout...")
    filename = create_printout(context)
    workingdir = os.path.abspath(os.getcwd())

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    debug(f"Function executed in {elapsed_time:.6f} seconds")

    return send_from_directory(workingdir, filename)

@app.route("/evidence/takehome", methods=["POST"])
def evidence_takehome():
    """A copy of the report for the client to take home. See takehome.py."""
    # The password comes from the form body only; it is not logged or stored.
    password = request.form.get("takehome_password", "")
    context = _printout_context("")
    data = create_takehome_pdf(context, password)
    return send_file(
        io.BytesIO(data),
        mimetype="application/pdf",
        download_name=neutral_filename(),
        as_attachment=True,
    )


@app.route("/evidence/delete-data", methods=["POST"])
def evidence_delete_data():

    delete_client_data()
    flash("Client data deleted successfully.", "success")
    return redirect(url_for('evidence_home'))

@app.route("/evidence/delete/account/<int:id>", methods=["POST"])
def evidence_delete_account(id):

    accounts = load_object_from_json(ConsultDataTypes.ACCOUNTS.value)
    for account in accounts:
        if account.account_id == id:

            # If we find the right account, delete it and save updated data
            accounts.remove(account)
            save_data_as_json(accounts, ConsultDataTypes.ACCOUNTS.value)
            flash("Account deleted successfully.", "success")
            return redirect(url_for('evidence_home'))

    flash("Account not found.", "warning")
    return redirect(url_for('evidence_home'))


@app.route("/evidence/delete/scan/<string:ser>", methods=["POST"])
def evidence_delete_scan(ser):

    all_scan_data = load_object_from_json(ConsultDataTypes.SCANS.value)
    current_scan = get_scan_by_ser(ser, all_scan_data)

    if current_scan and current_scan.serial == ser:
        all_scan_data.remove(current_scan)
        save_data_as_json(all_scan_data, ConsultDataTypes.SCANS.value)
        flash("Scan deleted successfully.", "success")
    else:
        flash("Scan not found.", "warning")

    return redirect(url_for('evidence_home'))
