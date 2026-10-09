"""Routes for scanning a device and investigating its apps (evidence workflow)."""
import traceback

import config
from evidence_collection import (
    AppInvestigationForm,
    AppSelectPageForm,
    ConsultDataTypes,
    ManualAddPageForm,
    ScanData,
    StartForm,
    get_scan_by_ser,
    get_scan_data,
    get_serial,
    load_object_from_json,
    remove_unwanted_data,
    save_data_as_json,
    update_scan_by_ser,
)
from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from web import app
from debuglog import debug, pdebug


USE_PICKLE_FOR_SUMMARY = False
USE_FAKE_DATA = True


@app.route("/evidence/scan", methods={'GET', 'POST'},
           defaults={'device_type': '', 'device_nickname': '', 'force_rescan': False})
@app.route("/evidence/scan/<device_type>/<device_nickname>", methods={'GET', 'POST'},
           defaults={'force_rescan': False})
@app.route("/evidence/scan/<device_type>/<device_nickname>/force-rescan", methods={'GET', 'POST'},
           defaults={'force_rescan': True})
def evidence_scan_start(device_type, device_nickname, force_rescan):

    # always assume we are starting with a fresh scan
    all_scan_data = load_object_from_json(ConsultDataTypes.SCANS.value)
    current_scan = ScanData()
    form = StartForm(device_type=device_type, device_nickname=device_nickname)

    context = dict(
        task = "evidence-scan",
        form = form,
        title=config.TITLE,
        scan_data = current_scan.to_dict(),
        step = 1,
        id = 0,
    )

    if request.method == "GET":
        pdebug(form.data)
        return render_template('main.html', **context)

    if request.method == "POST":
        pdebug(form.data)
        if form.is_submitted() and form.validate():

            if form.manualadd.data:

                # if it's a manual add, create a new scan object and redirect to the manual add page
                return redirect(url_for('evidence_scan_manualadd'))

            # clean up the submitted data
            clean_data = remove_unwanted_data(form.data)

            # Ensure any previous screenshots have been removed before scan
            # print("Removing files:")
            # os.system("ls webstatic/images/screenshots/")
            # os.system("rm webstatic/images/screenshots/*")

            # Do the above at end of consult instead

            try:
                # Before moving on, check if we're scanning a device we've already scanned.
                # If so, just load the next page for that device
                ser = get_serial(clean_data["device_type"], clean_data["device_nickname"])
                hmac_ser = config.hmac_serial(ser)
                debug("SERIAL NUMBER: " + hmac_ser)
                if not force_rescan:
                    for scan in all_scan_data:
                        if scan.serial == hmac_ser:
                            flash("This device was already scanned.")
                            return redirect(url_for('evidence_scan_select', ser=hmac_ser, show_rescan=True))

                # Perform the scan
                scan_data, suspicious_apps_dict, other_apps_dict = get_scan_data(clean_data["device_type"], clean_data["device_nickname"])

                # Fill in the /investigate/ marker for suspicious apps
                for i in range(len(suspicious_apps_dict)):
                    suspicious_apps_dict[i]["investigate"] = True

                all_apps = suspicious_apps_dict + other_apps_dict
                for a in all_apps:
                    a["device_serial_udid"] = ser

                # Create current scan object with this info
                current_scan = ScanData(scan_id=len(all_scan_data),
                                        **clean_data,
                                        **scan_data,
                                        all_apps=all_apps)

                current_scan.id = len(all_scan_data)

                # Add the scan to the list of all scans,
                # replacing any previous scan with the same serial number
                # or adding a new scan if it doesn't exist
                update_scan_by_ser(current_scan, all_scan_data)

                save_data_as_json(all_scan_data, ConsultDataTypes.SCANS.value)
                return redirect(url_for('evidence_scan_select', ser=current_scan.serial))

            except Exception as e:
                debug(traceback.format_exc())
                flash("Scan error: " + str(e))
                return redirect(url_for('evidence_scan_start',
                                        device_type=form.data["device_type"],
                                        device_nickname=form.data["device_nickname"]))

        elif not form.validate():
            flash("Form validation error. Raw error: {}".format(form.errors), 'error')

    return redirect(url_for('evidence_scan_start'))



@app.route("/evidence/scan/select/<string:ser>", methods={'GET', 'POST'}, defaults={'show_rescan': False})
@app.route("/evidence/scan/select/<string:ser>/show-rescan-<show_rescan>", methods={'GET', 'POST'})
def evidence_scan_select(ser, show_rescan):

    # load all scans
    all_scan_data = load_object_from_json(ConsultDataTypes.SCANS.value)

    # get the right scan by serial number
    current_scan = get_scan_by_ser(ser, all_scan_data)
    assert current_scan.serial == ser

    pdebug(current_scan.all_apps[0].permission_info.__dict__)

    # fill form
    form = AppSelectPageForm(apps=[app.to_dict() for app in current_scan.all_apps])

    # IF IT'S A GET:
    if request.method == 'GET':
        #form.process(data=current_scan.to_dict())

        context = dict(
            task = "evidence-scan",
            form = form,
            device = current_scan.device_type,
            nickname = current_scan.device_nickname,
            title=config.TITLE,
            all_apps = [app.to_dict() for app in current_scan.all_apps],
            is_rooted = current_scan.is_rooted,
            rooted_reasons = current_scan.rooted_reasons,
            step = 2,
            num_sys_apps = len([app for app in current_scan.all_apps if 'system-app' in app.flags]),
            show_rescan = show_rescan,
            serial=current_scan.serial,
            serial_or_udid=current_scan.serial_or_udid
        )
        debug("-"*80)
        debug(context['device'])
        debug("-"*80)

        return render_template('main.html', **context)

    # Submit the form if it's a POST
    if request.method == 'POST':
        pdebug(form.data)
        if form.is_submitted() and form.validate():

            # clean up the submitted data
            #clean_data = remove_unwanted_data(form.data)

            # get selected apps from the form data
            to_investigate_ids = [app["appId"] for app in form.data['apps'] if app['investigate']]

            # Remove apps we no longer want to investigate,
            # while maintaining info from previous investigations
            current_scan.selected_apps = [app for app in current_scan.selected_apps if app.appId in to_investigate_ids]

            # Update "investigate" marker and add new apps to selected_apps
            # TODO: Do we need the "investigate" marker?
            for a in current_scan.all_apps:
                if a.appId in to_investigate_ids:

                    # If this wasn't marked for investigation,
                    # or if it was but we don't have it in selected_apps,
                    # then add it to selected_apps
                    matching_apps = [app for app in current_scan.selected_apps if app.appId == a.appId]
                    if not a.investigate or len(matching_apps) == 0:
                        current_scan.selected_apps.append(a)

                    # Mark that we investigated this app
                    a.investigate = True

                else:
                    a.investigate = False

            # update the current scan data and save it as the most recent scan
            # current_scan.selected_apps = [AppInfo(**app) for app in selected_apps]
            all_scan_data = update_scan_by_ser(current_scan, all_scan_data)

            # save this updated data
            save_data_as_json(all_scan_data, ConsultDataTypes.SCANS.value)

            return redirect(url_for('evidence_scan_investigate', ser=ser))

        if not form.validate():
            flash("Form validation error. Raw error: {}".format(form.errors), 'error')

        return redirect(url_for('evidence_scan_select'), ser=ser)

@app.route("/evidence/scan/manualadd/", methods={'GET', 'POST'}, defaults={'ser': None})
@app.route("/evidence/scan/manualadd/<string:ser>", methods={'GET', 'POST'})
def evidence_scan_manualadd(ser):

    current_scan = ScanData()

    # If we passed a serial number, load the scan data for that serial
    if ser:
        all_scan_data = load_object_from_json(ConsultDataTypes.SCANS.value)
        current_scan = get_scan_by_ser(ser, all_scan_data)
        assert current_scan.serial == ser
    else:
        current_scan.manual = True

    manual_add_apps = [{"app_name": app.title, "spyware": "spyware" in app.flags}
                       for app in current_scan.selected_apps]

    form = ManualAddPageForm(apps = manual_add_apps,
                             device_nickname=current_scan.device_nickname,
                             device_manufacturer=current_scan.device_manufacturer,
                             device_model=current_scan.device_model,
                             device_version=current_scan.device_version,
                             device_serial=current_scan.serial,
                             is_rooted="yes" if current_scan.is_rooted else "none",
                             rooted_reasons=current_scan.rooted_reasons)

    ### IF IT'S A GET:
    if request.method == 'GET':

        context = dict(
            task = "evidence-scan-manualadd",
            title = config.TITLE,
            form = form
        )

        return render_template('main.html', **context)

    ### IF IT'S A POST:
    if request.method == 'POST':

        if form.is_submitted():

            # if it's an addline request, do that and reload
            if form.addline.data:
                form.update_self()
                context = dict(
                    task = "evidence-scan-manualadd",
                    title = config.TITLE,
                    form = form
                )
                return render_template('main.html', **context)

            elif form.validate():
                # Get scan details that were manually added
                current_scan.device_nickname = form.data['device_nickname']
                current_scan.device_model = form.data['device_model']
                current_scan.device_version = form.data['device_version']
                current_scan.device_manufacturer = form.data['device_manufacturer']
                current_scan.is_rooted = form.data['is_rooted'] == 'yes'
                current_scan.rooted_reasons = form.data['rooted_reasons']

                # Input serial or make a fake one if needed
                current_scan.serial = form.data['device_serial']
                if current_scan.serial.strip() == "":
                    current_scan.serial = "MANADD-" + current_scan.device_nickname.replace(" ", "-")

                # Add apps that were manually added to selected_apps and all_apps
                selected_apps = []
                for a in form.data['apps']:
                    flags = []
                    if a['spyware']:
                        flags.append('spyware')
                    if a['dualuse']:
                        flags.append('dual-use')
                    if a['app_name'].strip() != "":
                        selected_apps.append({
                            "title": a['app_name'],
                            "investigate": True,
                            "flags": flags
                        })

                current_scan.all_apps = selected_apps
                current_scan.selected_apps = selected_apps

                # load all scans
                all_scan_data = load_object_from_json(ConsultDataTypes.SCANS.value)

                # add manual scan
                all_scan_data = update_scan_by_ser(current_scan, all_scan_data)

                # save
                save_data_as_json(all_scan_data, ConsultDataTypes.SCANS.value)

                return redirect(url_for('evidence_scan_investigate', ser=current_scan.serial))

            if not form.validate():
                flash("Form validation error. Raw error: {}".format(form.errors), 'error')

            return redirect(url_for('evidence_scan_manualadd', ser=ser))


@app.route("/evidence/scan/investigate/<string:ser>", methods={'GET', 'POST'})
def evidence_scan_investigate(ser):

    # load all scans
    all_scan_data = load_object_from_json(ConsultDataTypes.SCANS.value)

    # get the right scan by serial number
    current_scan = get_scan_by_ser(ser, all_scan_data)
    assert current_scan.serial == ser

    for a in current_scan.selected_apps:
        a = a.to_dict()
        pdebug("App: {}  Flags: {}".format(a["title"], a["flags"]))
    pdebug("INFO GIVEN TO INVESTIGATION FORM")

    form = AppInvestigationForm(selected_apps=[a.to_dict() for a in current_scan.selected_apps])

    ### IF IT'S A GET:
    if request.method == 'GET':

        context = dict(
            task = "evidence-scan",
            form = form,
            title=config.TITLE,
            scan_data = current_scan.to_dict(),
            device = current_scan.device_type,
            step = 3
        )

        return render_template('main.html', **context)


    # Submit the form if it's a POST
    if request.method == 'POST':
        pdebug(form.data)
        if form.is_submitted() and form.validate():

            # clean up the submitted data
            clean_data = remove_unwanted_data(form.data)

            # Update app info in selected_apps based on what was provided in the form
            for a in current_scan.selected_apps:
                for form_app in clean_data["selected_apps"]:
                    if a.appId == form_app["appId"]:
                        a.install_info = form_app["install_info"]
                        a.permission_info.access = form_app["permission_info"]["access"]
                        a.permission_info.describe = form_app["permission_info"]["describe"]
                        a.notes = form_app["notes"]

            all_scan_data = update_scan_by_ser(current_scan, all_scan_data)

            #  save this updated data
            save_data_as_json(all_scan_data, ConsultDataTypes.SCANS.value)

            return redirect(url_for('evidence_home'))

        elif not form.validate():
            flash("Form validation error. Raw error: {}".format(form.errors), 'error')
            return redirect(url_for('evidence_scan_investigate', ser=ser))

    return redirect(url_for('evidence_scan_investigate', ser=ser))
