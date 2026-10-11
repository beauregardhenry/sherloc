"""Apps found on a device and the scan that found them."""
from evidence_base import DictInitClass, Dictable, Notes, Risk, RiskReport, ScreenshotInfo


class InstallInfo(DictInitClass):
    questions = {
        'knew_installed': 'Did you know this app was installed?',
        'installed': 'Did you install this app?',
        'coerced': 'Did the person of concern coerce you into installing this app?'
    }
    attrs = list(questions.keys())

    def generate_risk_report(self, system_app = False):
        risks = list()

        if not system_app:
            if self.knew_installed == 'no' or self.installed == 'no' or self.coerced == 'yes':

                description = ""
                if self.knew_installed == 'no':
                    description = "The client did not know this app was installed, indicating someone else installed it."

                elif self.installed == 'no':
                    description = "The client did not install this app, indicating someone else installed it."

                elif self.coerced == 'yes':
                    description = "The client was coerced into installing this app."

                new_risk = Risk(
                    risk="App installed without permission",
                    description=description
                )
                risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)
        return self.risk_report


class PermissionInfo(DictInitClass):
    questions = {
        "access": "Is any information being leaked to the person of concern through this app?",
        "describe": "If yes, please describe."
    }
    attrs = ['permissions',
             'access',
             'describe']

    def generate_risk_report(self):
        risks = list()

        if self.access == 'yes':
            new_risk = Risk(
                risk="Data leakage",
                description="This app is sharing data with the person of concern."
            )
            risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)
        return self.risk_report


class AppInfo(Dictable):
    def __init__(self,
                 title="",
                 app_name="",
                 appId="",
                 install_time="",
                 app_version="",
                 last_updated="",
                 flags=None,
                 application_icon="",
                 app_website="",
                 description="",
                 developerwebsite="",
                 investigate=False,
                 permission_info=None,
                 permissions=None,
                 install_info=None,
                 notes=None,
                 device_serial_udid="",
                 **kwargs):

        if flags is None:
            flags = []
        if permission_info is None:
            permission_info = dict()
        if permissions is None:
            permissions = []
        if install_info is None:
            install_info = dict()
        if notes is None:
            notes = dict()
        self.title = title
        self.app_name = app_name
        if self.app_name.strip() == "":
            self.app_name = title
        if self.title.strip() == "":
            self.title = app_name
        if self.app_name.strip() == "" or self.app_name.strip() == "App":
            self.app_name = appId
            self.title = appId
        self.appId = appId

        self.install_time = install_time
        self.app_version = app_version
        self.last_updated = last_updated

        # Fill in flags, removing any flags == ""
        self.flags = list(filter(None, flags))

        self.application_icon = application_icon
        self.app_website = app_website
        self.description = description
        self.developerwebsite = developerwebsite
        self.investigate = investigate

        # I DON"T REALLY KNOW WHY THE BELOW LOGIC IS NECESSARY

        # If permission_info is empty, then we need to create
        # a new PermissionInfo object with the permissions
        if len(permission_info) == 0:
            self.permission_info = PermissionInfo({
                'permissions': permissions
            })

        # Otherwise, create a PermissionInfo object with the provided data
        else:
            self.permission_info = PermissionInfo(permission_info)

        self.install_info = InstallInfo(install_info)
        self.notes = Notes(notes)

        self.device_serial_udid = device_serial_udid
        self.screenshot_files = list()
        self.screenshot_info = list()

    def set_screenshot_files(self, screenshot_files):
        self.screenshot_files = screenshot_files

    def create_screenshot_info(self, get_metadata=True):
        '''
        Creates screenshot objects for all screenshot files related to this app.
        '''
        self.screenshot_info = [ScreenshotInfo(
            fname=fname,
            context="app",
            app_id=self.appId,
            app_name=self.app_name,
            device_serial=self.device_serial_udid,
            get_metadata=get_metadata
        ) for fname in self.screenshot_files]

        return self.screenshot_info

    def _get_flag_risk(self):
        if 'spyware' in self.flags or 'onstore-spyware' in self.flags or 'offstore-spyware' in self.flags:
            return Risk(
                risk="Spyware application",
                description="This app is designed for covert surveillance."
            )
        elif 'regex-spy' in self.flags:
            return Risk(
                risk="Potential spyware application",
                description="This app may be a spyware application based on its title and description."
            )
        return None

    def generate_risk_report(self):
        '''
        Generate a risk report about this app. Possible risks:
            - Flag-based concerns (spyware, offstore)
            - App installed without permission (accounting for system apps)
            - App is sharing data
        '''
        risks = list()

        # Flag-based risk
        flag_risk = self._get_flag_risk()
        if flag_risk:
            risks.append(flag_risk)

        # Data leakage
        data_risks = self.permission_info.generate_risk_report()
        risks.extend(data_risks.risk_details)

        # Installation issues
        install_risks = self.install_info.generate_risk_report(system_app='system-app' in self.flags)
        risks.extend(install_risks.risk_details)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class ScanData(Dictable):
    def __init__(self,
                 manual=False,
                 scan_id=0,
                 device_type="",
                 device_nickname="",
                 serial="",
                 adb_serial="",
                 serial_or_udid="",  # TODO: Just use this one
                 device_model="",
                 device_version="",
                 device_manufacturer="",
                 is_rooted="",
                 rooted_reasons="",
                 all_apps=None,
                 selected_apps=None,
                 **kwargs):

        if all_apps is None:
            all_apps = list()
        if selected_apps is None:
            selected_apps = list()
        self.manual = manual
        self.scan_id = scan_id
        self.device_type = device_type
        self.device_nickname = device_nickname
        self.serial = serial
        self.serial_or_udid = serial_or_udid
        if self.serial_or_udid.strip() == "":
            self.serial_or_udid = adb_serial
        self.device_model = device_model
        self.device_version = device_version
        self.device_manufacturer = device_manufacturer
        self.is_rooted = is_rooted
        self.rooted_reasons = rooted_reasons

        # sort all_apps by title, with system apps at the end,
        # checked apps at the top, and flagged investigated apps at the top top
        self.all_apps = [AppInfo(**app) for app in all_apps]
        self.all_apps.sort(key=lambda x: x.title.lower())
        self.all_apps.sort(key=lambda x: len(x.flags) > 0, reverse=True)
        self.all_apps.sort(key=lambda x: 'system-app' in x.flags and len(x.flags) == 1)
        self.all_apps.sort(key=lambda x: x.investigate, reverse=True)

        self.selected_apps = [AppInfo(**app) for app in selected_apps]

        self.screenshot_files = list()
        self.screenshot_info = list()

        self.generate_risk_report()

    def set_screenshot_files(self, screenshot_files):
        self.screenshot_files = screenshot_files

    def create_screenshot_info(self, get_metadata=True):
        '''
        Creates screenshot objects for all screenshot files related to this device scan.
        '''
        self.screenshot_info = [ScreenshotInfo(
            fname=fname,
            context="root",
            device_nickname=self.device_nickname,
            device_serial=self.serial,
            get_metadata=get_metadata
        ) for fname in self.screenshot_files]

        return self.screenshot_info

    def generate_risk_report(self):
        '''
        Generate a risk report for this device. Possible risks:
            - Jailbroken device
            - Risk from installed apps (raise up from apps)
        '''
        risks = list()
        self.concerning_apps = list()

        if self.is_rooted:
            new_risk = Risk(
                risk="Evidence of jailbreaking",
                description="The device may be jailbroken, giving the person of concern nearly unbounded access to the device and the client's activity on the device."
            )
            risks.append(new_risk)

        # Apps
        for a in self.selected_apps:
            app_risk_report = a.generate_risk_report()
            if app_risk_report.risk_present:
                self.concerning_apps.append(a)
                app_risk_list = [r.risk for r in app_risk_report.risk_details]
                new_risk = Risk(
                    risk="Risk from app: {}".format(a.title),
                    description="Risks identified: {}.".format(", ".join(app_risk_list))
                )
                risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report
