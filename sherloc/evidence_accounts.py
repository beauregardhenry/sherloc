"""Account investigation sections (logins, password, recovery, 2FA, security questions)."""
import os
import re
from evidence_base import DictInitClass, Dictable, Notes, Risk, RiskReport, ScreenshotInfo


class AccountSection(DictInitClass):
    screenshot_label = ""
    attrs = ["account_id"]

    def __init__(self, datadict=None):
        if datadict is None:
            datadict = dict()
        super(AccountSection, self).__init__(datadict=datadict)
        self.screenshot_files = list()
        self.screenshot_info = list()

    def set_screenshot_files(self, screenshot_files):
        self.screenshot_files = screenshot_files

    def create_screenshot_info(self, get_metadata=True):
        '''
        Creates screenshot objects for all screenshot files related to this account section.
        '''
        self.screenshot_info = [ScreenshotInfo(
            fname=fname,
            context="account",
            get_metadata=get_metadata
        ) for fname in self.screenshot_files]

        return self.screenshot_info


class SuspiciousLogins(AccountSection):
    questions = {
        'recognize': "Do you see any unrecognized devices that are logged into this account?",
        'describe_logins': "Which devices do you not recognize?",
        'activity_log': "In the login history, do you see any suspicious logins?",
        'describe_activity': "Which logins are suspicious, and why?"
    }
    attrs = AccountSection.attrs + list(questions.keys())
    screenshot_label = "suspicious_logins"

    def generate_risk_report(self):
        '''
        Generate a risk report about suspicious logins. Possible risks:
            - Unrecognized devices
            - Suspicious logins
        '''
        risks = list()

        if self.recognize == 'yes':
            new_risk = Risk(
                risk = "Unrecognized devices",
                description = "There are unrecognized devices currently logged into this account."
            )
            risks.append(new_risk)

        if self.activity_log == 'yes':
            new_risk = Risk(
                risk = "Suspicious logins",
                description = "There are suspicious logins to this account that do not appear to have come from the client."
            )
            risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class PasswordCheck(AccountSection):
    questions = {
        "last_updated": "When did you last update this password (approximately)?",
        "know": "Does the person of concern know the password for this account?",
        "guess": "Do you believe the person of concern could guess the password?",
        "federated": "Do you log into this account using a federated login (e.g., Google, Facebook, Apple)?",
        "federated_which": "What other account do you use to log in?",
        "federated_comp": "Do you believe the person of concern has access to the federated account?",
    }
    attrs = AccountSection.attrs + list(questions.keys())

    def __init__(self, datadict=None):
        if datadict is None:
            datadict = dict()
        super(PasswordCheck, self).__init__(datadict=datadict)

    def generate_risk_report(self):
        '''
        Generate a risk report about password knowledge. Possible risks:
            - Knowledge of passwords
            - Ability to guess password
        '''
        risks = list()

        if self.know == 'yes':
            new_risk = Risk(
                risk = "Password compromise",
                description = "Knowing the password to this account could enable the person of concern to log in. (Note: If two-factor authentication is enabled, they would still need to bypass the second factor.)"
            )
            risks.append(new_risk)

        elif self.guess == 'yes':
            new_risk = Risk(
                risk = "Potential password compromise",
                description = "The client believes the person of concern could guess the password for this account. If they guess correctly, it would enable them to log in. (Note: If two-factor authentication is enabled, they would still need to bypass the second factor.)"
            )
            risks.append(new_risk)

        if self.federated_comp == "yes":
            new_risk = Risk(
                risk = "Compromised federated account",
                description = "By compromising the federated account, the person of concern could log into this account without needing to know the password."
            )
            risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class RecoverySettings(AccountSection):
    questions = {
        'phone_present': "Is there a recovery phone number set for this account?",
        'phone': "What is the recovery phone number?",
        'phone_access': "Do you believe the person of concern has access to the recovery phone number?",
        'email_present': "Is there a recovery email address set for this account?",
        'email': "What is the recovery email address?",
        'email_access': "Do you believe the person of concern has access to this recovery email address?"
    }
    attrs = AccountSection.attrs + list(questions.keys())
    screenshot_label = "recovery_settings"

    def generate_risk_report(self):
        '''
        Generate a risk report about recovery settings. Possible risks:
            - Recovery settings compromised
        '''
        risks = list()

        if self.phone_access == 'yes' or self.email_access == 'yes':
            new_risk = Risk(
                risk = "Compromised recovery information",
                description = "With access to the recovery contact information, someone can access an account without knowing the password using the 'Forgot password' option."
            )
            risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class TwoFactorSettings(AccountSection):
    questions = {
        'enabled': "Is two-factor authentication enabled for this account?",
        'second_factor_type': "What type of two-factor authentication is used?",
        'describe': "Which phone/email/app is set as the second factor?",
        'second_factor_access': "Do you believe the person of concern has access to this second factor?",
    }
    attrs = AccountSection.attrs + list(questions.keys())
    screenshot_label = "two_factor_settings"

    def generate_risk_report(self):
        '''
        Generate a risk report about two factor settings. Possible risks:
            - Two factor not set
            - 2nd factor compromised
        '''
        risks = list()

        if self.second_factor_access == 'yes':
            new_risk = Risk(
                risk = "Compromised second factor",
                description = "If someone has access to the second authentication factor, they only need the account password to log into the account. They could also intercept and delete login notifications."
            )
            risks.append(new_risk)

        elif self.enabled == 'no':
            new_risk = Risk(
                risk = "Two-factor authentication disabled",
                description = "Without two-factor authentication, others only need the account password to log in."
            )
            risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class SecurityQuestions(AccountSection):
    questions = {
        'present': "Does the account use security questions?",
        'know': "Do you believe the person of concern knows the answer to any of these questions?",
        'which': "Which questions might they be able to answer?",
    }
    attrs = AccountSection.attrs + list(questions.keys())
    screenshot_label = "security_questions"

    def generate_risk_report(self):
        '''
        Generate a risk report about security questions. Possible risks:
            - Enabled
            - Known
        '''
        risks = list()

        if self.present == 'yes':

            if self.know == 'yes':
                new_risk = Risk(
                    risk = "Guessable security questions",
                    description = "The client believes the person of concern knows the answers to security questions, which could allow them an easy way to log into the account."

                )
                risks.append(new_risk)

            else:
                new_risk = Risk(
                    risk = "Use of security questions",
                    description = "The account allows login using security questions, which are not secure because they are easy to guess."
                )
                risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class AccountInvestigation(Dictable):
    def __init__(self,
                 account_id=0,
                 platform="",
                 username="",
                 suspicious_logins=None,
                 password_check=None,
                 recovery_settings=None,
                 two_factor_settings=None,
                 security_questions=None,
                 notes=None,
                 **kwargs):
        if suspicious_logins is None:
            suspicious_logins = dict()
        if password_check is None:
            password_check = dict()
        if recovery_settings is None:
            recovery_settings = dict()
        if two_factor_settings is None:
            two_factor_settings = dict()
        if security_questions is None:
            security_questions = dict()
        if notes is None:
            notes = dict()
        self.account_id = account_id
        self.platform = platform
        self.username = username

        # insert account id where needed to get screenshots
        for section in [suspicious_logins, recovery_settings, two_factor_settings, security_questions]:
            section['account_id'] = account_id
        self.suspicious_logins = SuspiciousLogins(suspicious_logins)
        self.password_check = PasswordCheck(password_check)
        self.recovery_settings = RecoverySettings(recovery_settings)
        self.two_factor_settings = TwoFactorSettings(two_factor_settings)
        self.security_questions = SecurityQuestions(security_questions)
        self.notes = Notes(notes)

        self.generate_risk_report()


    def generate_risk_report(self):

        risks = list()

        for obj in [self.suspicious_logins, self.password_check, self.recovery_settings, self.two_factor_settings, self.security_questions]:
            risk_report: RiskReport = obj.generate_risk_report()
            risks.extend(risk_report.risk_details)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


def get_all_screenshot_files():
    '''
    Gather all screenshot files at once. This will greatly speed up
    compiling screenshot filenames.

    Returns screenshot_files, a dict() with keys:
        - devices: [serial] -> dict():
            - "root" -> list of screenshots
            - [app id] -> list of screenshots
        - account_sections: account id (str) -> dict() with keys:
            - [section label] -> list of screenshots
    '''

    # Everything is in SCREENSHOT_DIR under a device serial number
    # Need to get:
    #   - Device jailbreak (<device ser>/rooting/)
    #   - Device apps (<device ser>/<appid>/)
    #   - Account sections (<any ser>/account<id>_<section>/)

    screenshot_files = dict(
        devices = dict(),  # accessed by ser
        account_sections = dict()  # accessed by account id as a string
    )

    account_pattern = re.compile(r"account\d+_[a-zA-Z_]+")

    overall_screenshot_dir = os.path.join("webstatic", "images", "screenshots")
    if os.path.exists(overall_screenshot_dir):

        # go into all device dirs and subdirs
        device_dirs = [f for f in os.scandir(overall_screenshot_dir) if os.path.isdir(f)]
        for device_dir in device_dirs:
            screenshot_dirs = [f for f in os.scandir(device_dir.path) if os.path.isdir(f)]

            for screenshot_dir in screenshot_dirs:
                # get all screenshot files from this directory
                files = os.listdir(screenshot_dir.path)
                full_fnames = [os.path.join(screenshot_dir, f) for f in files]
                full_fnames.sort()

                if len(full_fnames) > 0:

                    # save the fnames in the right place
                    if screenshot_dir.name == "rooting":
                        if device_dir.name not in list(screenshot_files["devices"].keys()):
                            screenshot_files["devices"][device_dir.name] = dict(
                                root = list()
                            )

                        screenshot_files["devices"][device_dir.name]["root"] = full_fnames

                    elif account_pattern.match(screenshot_dir.name):
                        fname_parts = screenshot_dir.name.split("_", 1)
                        account_id_str = fname_parts[0][-1]
                        account_section = fname_parts[1]

                        if account_id_str not in list(screenshot_files["account_sections"].keys()):
                            section_dict = dict()
                            section_dict[SuspiciousLogins().screenshot_label] = list()
                            section_dict[RecoverySettings().screenshot_label] = list()
                            section_dict[TwoFactorSettings().screenshot_label] = list()
                            section_dict[SecurityQuestions().screenshot_label] = list()
                            screenshot_files["account_sections"][account_id_str] = section_dict

                        screenshot_files["account_sections"][account_id_str][account_section].extend(full_fnames)

                    else:
                        # add if needed
                        if device_dir.name not in list(screenshot_files["devices"].keys()):
                            screenshot_files["devices"][device_dir.name] = dict(
                                root = list()
                            )

                        screenshot_files["devices"][device_dir.name][screenshot_dir.name] = full_fnames

    return screenshot_files
