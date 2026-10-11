"""Whole-consultation data classes. The domain classes live in the evidence_* modules;
they are re-exported here so `from evidence_model import X` keeps working."""
from evidence_base import (  # noqa: F401
    EvidenceDataEncoder,
    Dictable,
    DictInitClass,
    Risk,
    RiskReport,
    Notes,
    ScreenshotInfo,
)
from evidence_accounts import (  # noqa: F401
    AccountSection,
    SuspiciousLogins,
    PasswordCheck,
    RecoverySettings,
    TwoFactorSettings,
    SecurityQuestions,
    AccountInvestigation,
    get_all_screenshot_files,
)
from evidence_apps import (  # noqa: F401
    InstallInfo,
    PermissionInfo,
    AppInfo,
    ScanData,
)
from evidence_taq import (  # noqa: F401
    TAQDevices,
    TAQAccounts,
    TAQSharing,
    TAQSmarthome,
    TAQKids,
    TAQLegal,
    TAQData,
)


### REAL CLASSES

class ConsultationData(Dictable):

    def __init__(self,
                 setup = None,
                 taq = None,
                 accounts = None,
                 scans = None,
                 screenshot_dir = "",
                 notes = None,
                 **kwargs):
        # Note: Not used except in printout.
        if setup is None:
            setup = dict()
        if taq is None:
            taq = dict()
        if accounts is None:
            accounts = []
        if scans is None:
            scans = []
        if notes is None:
            notes = dict()
        self.setup = ConsultSetupData(**setup)

        self.taq = TAQData(**taq)
        self.accounts = [AccountInvestigation(**account) for account in accounts]
        self.scans = [ScanData(**scan) for scan in scans]
        self.screenshot_dir = screenshot_dir
        self.notes = ConsultNotesData(**notes)

        # Grab questions that we will use to generate the printout
        # TODO: streamline
        self.formquestions = dict()
        self.formquestions["accounts"] = dict(
            suspicious_logins = SuspiciousLogins().questions,
            password_check = PasswordCheck().questions,
            recovery_settings = RecoverySettings().questions,
            two_factor_settings = TwoFactorSettings().questions,
            security_questions = SecurityQuestions().questions
        )
        self.formquestions["taq"] = dict(
            devices = TAQDevices().questions,
            accounts = TAQAccounts().questions,
            sharing = TAQSharing().questions,
            smarthome = TAQSmarthome().questions,
            kids = TAQKids().questions,
            legal = TAQLegal().questions
        )
        self.formquestions["apps"] = dict(
            permission_info = PermissionInfo().questions,
            install_info = InstallInfo().questions
        )

    def prepare_reports(self):
        '''
        Create all risk reports for the elements of the consultation.
        '''
        self.taq.generate_risk_reports()
        for scan in self.scans:
            scan.generate_risk_report()
        for account in self.accounts:
            account.generate_risk_report()

    def prepare_screenshots(self, get_metadata=True):
        """
        Get all screenshot information for the consultation.
        """

        all_screenshots = get_all_screenshot_files()

        for scan in self.scans:
            if scan.serial_or_udid in list(all_screenshots["devices"].keys()):
                scan_screenshots = all_screenshots["devices"][scan.serial_or_udid]

                scan_root_screenshots = scan_screenshots.get("root", list())
                scan.set_screenshot_files(scan_root_screenshots)
                scan.create_screenshot_info(get_metadata=get_metadata)

                for app in scan.selected_apps:
                    app_screenshots = scan_screenshots.get(app.appId, list())
                    app.set_screenshot_files(app_screenshots)
                    app.create_screenshot_info(get_metadata=get_metadata)

        for account in self.accounts:
            if str(account.account_id) in list(all_screenshots["account_sections"].keys()):
                for section in [account.recovery_settings,
                                account.security_questions,
                                account.suspicious_logins,
                                account.two_factor_settings]:
                    section_screenshots = all_screenshots["account_sections"][str(account.account_id)][section.screenshot_label]
                    section.set_screenshot_files(section_screenshots)
                    section.create_screenshot_info(get_metadata=get_metadata)


class ConsultSetupData(Dictable):
    def __init__(self,
                 client="",
                 date="",
                 **kwargs):
        self.client = client
        self.date = date


class ConsultNotesData(Dictable):
    def __init__(self,
                 consultant_notes="",
                 client_notes="",
                 **kwargs):
        self.consultant_notes = consultant_notes
        self.client_notes = client_notes
