"""Technology assessment questionnaire (TAQ) answers."""
from evidence_base import DictInitClass, Dictable, Risk, RiskReport


class TAQDevices(DictInitClass):
    questions = {
        'live_together': "Do you live with the person of concern?",
        'purchase_device': "Did the person of concern purchase and/or set up any of your devices?",
        'purchase_device_which': "Which devices did the person of concern purchase and/or set up?",
        'physical_access': "Has the person of concern had physical access to your devices at any point in time?",
        'physical_access_which': "To which devices has the person of concern had physical access?",
        'device_pin': "Can the person of concern unlock any of these devices with PIN, password, or biometrics?",
    }
    attrs = list(questions.keys())

    def generate_risk_report(self) -> RiskReport:
        '''
        Generate a risk report for device compromise. Possible risk:
            - Physical access to devices
        '''
        risks = list()

        # Both indicate the same thing: physical access to devices.
        if self.live_together.lower() == 'yes' or self.physical_access.lower() == 'yes' or self.purchase_device.lower() == 'yes':
            new_risk = Risk(
                risk="Physical access to devices",
                description="A person with physical access to devices might be able to install apps, adjust device configurations, and access or manipulate accounts logged in on that device."
            )
            if self.device_pin.lower() == 'yes':
                new_risk.description += " They can also unlock the device with a PIN, password, or biometrics, which would allow them to access all data on the device."
            risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class TAQAccounts(DictInitClass):
    questions = {'pwd_mgmt': "How do you remember your passwords?",
                 'pwd_mgmt_describe': "Please provide more details on how you remember your passwords.",
                 'pwd_comp': "Do you believe the person of concern knows, or could guess, any of your passwords?",
                 'pwd_comp_which': "Which passwords do you believe are compromised, and why?"}
    attrs = list(questions.keys())

    def generate_risk_report(self) -> RiskReport:
        '''
        Generate a risk report for password compromise. Possible risks:
            - Password compromise
            - Password manager compromise TODO
        '''
        risks = list()

        if self.pwd_comp == 'yes':
            new_risk = Risk(
                risk="Password compromise",
                description="Someone who knows account passwords may be able to access and/or manipulate those accounts."
            )
            risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class TAQSharing(DictInitClass):
    questions = {'share_phone_plan': "Do you share a phone plan with the person of concern?",
                 'phone_plan_admin': "If you share a phone plan, who is the family 'head' or plan administrator?",
                 'share_accounts': "Do you share any accounts with the person of concern?",
                 'share_which': "Which accounts are shared with the person of concern?"}
    attrs = list(questions.keys())

    def generate_risk_report(self) -> RiskReport:
        '''
        Generate a risk report for account compromise due to sharing. Possible risks:
            - Shared phone plan
            - Shared accounts
        '''
        risks = list()

        if self.share_phone_plan == 'yes':
            new_risk = Risk(
                risk="Shared phone plan",
                description="A shared phone plan may leak a variety of information, possibly including call history, message history (but not message content), contacts, and sometimes location. The account administrator of the client's phone plan has even more privileged access to this information."
            )
            # Going to need to reformat the administrator here bc it'll probably say 'poc' not spelled out
            risks.append(new_risk)

        if self.share_accounts == 'yes':
            new_risk = Risk(
                risk="Shared accounts",
                description="The client has shared accounts with the person of concern. Any information on those accounts can be assumed to be known by the person of concern."
            )
            risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class TAQSmarthome(DictInitClass):
    questions = {'smart_home': "Do you have any smart home devices?",
                 'smart_home_setup': "Who installed and set up your smart home devices?",
                 'smart_home_access': "Did the person of concern ever have physical access to the devices?",
                 'smart_home_acct_sharing': "Do you share any smart home accounts with the person of concern?",
                 'smart_home_acct_linking': "Can the person of concern access any of the smart home devices via their own smart home account?"}
    attrs = list(questions.keys())

    def _get_phys_access_risk(self):
        if self.smart_home_setup == 'poc':  # Check that this is what it would be, and not "Person of Concern"
            return Risk(
                risk="Physical access to smart home devices",
                description="With physical access to smart home devices, someone could (1) learn private information, for example by querying a smart speaker, or (2) reconfigure the devices to share information or allow remote control. Someone who initially set up the devices would have even more power to configure as they wish."
            )
        elif self.smart_home_access == 'yes':
            return Risk(
                risk="Physical access to smart home devices",
                description="With physical access to smart home devices, someone could (1) learn private information, for example by querying a smart speaker, or (2) reconfigure the devices to share information or allow remote control."
            )
        return None

    def _get_online_access_risk(self):
        if self.smart_home_acct_sharing == 'yes' or self.smart_home_acct_linking == 'yes':
            return Risk(
                risk="Online access to smart home devices",
                description="Someone with online access to a smart home device might be able to gather data (e.g., viewing video recordings or voice commands used) or manipulate the device state (e.g., turning a light off or locking a smart lock.)"
            )
        return None

    def generate_risk_report(self) -> RiskReport:
        '''
        Generate a risk report for smart home device compromise. Possible risks:
            - Physical access to smart home devices
            - Online access to smart home devices
        '''
        risks = list()

        # Physical access
        phys_access_risk = self._get_phys_access_risk()
        if phys_access_risk:
            risks.append(phys_access_risk)

        # Online access
        online_access_risk = self._get_online_access_risk()
        if online_access_risk:
            risks.append(online_access_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class TAQKids(DictInitClass):
    questions = {
        'custody': "If you have children, do they have electronic devices?",
        'child_phys_access': "Has the person of concern had physical access to any of the child(ren)'s devices?",
        'child_phone_plan': "Does the person of concern pay for the child(ren)'s phone plan?"}
    attrs = list(questions.keys())

    def generate_risk_report(self) -> RiskReport:
        '''
        Generate a risk report for children's devices. Possible risks:
            - Physical access to devices
            - Shared phone plan
            - TODO: Other things like accounts shared, location sharing, ??
        '''
        risks = list()

        if self.child_phys_access == 'yes':
            new_risk = Risk(
                risk="Physical access to children's devices",
                description="A person with physical access to children's devices might be able to install apps, adjust device configurations, and access or manipulate accounts logged in on that device. These changes could allow monitoring of the parent, for example by tracking the children's location when they are with their parent."
            )
            risks.append(new_risk)

        if self.child_phone_plan == 'yes':
            new_risk = Risk(
                risk="Shared phone plan (child)",
                description="A shared phone plan may leak a variety of information, possibly including call history, message history (but not message content), contacts, and sometimes location. This could include information about the parent, such as their phone number and location when with the children. The plan administrator has even more privileged access to this information."
            )
            # Going to need to reformat the administrator here bc it'll probably say 'poc' not spelled out
            risks.append(new_risk)

        self.risk_report = RiskReport(risk_details=risks)

        return self.risk_report


class TAQLegal(DictInitClass):
    questions = {
        'legal': "Do you have any ongoing or upcoming legal cases?",
    }
    attrs = list(questions.keys())


class TAQData(Dictable):

    def __init__(self,
                 marked_done=False,
                 devices=None,
                 accounts=None,
                 sharing=None,
                 smarthome=None,
                 kids=None,
                 legal=None,
                 **kwargs):
        if devices is None:
            devices = dict()
        if accounts is None:
            accounts = dict()
        if sharing is None:
            sharing = dict()
        if smarthome is None:
            smarthome = dict()
        if kids is None:
            kids = dict()
        if legal is None:
            legal = dict()
        self.marked_done = marked_done
        self.devices = TAQDevices(devices)
        self.accounts = TAQAccounts(accounts)
        #if self.accounts.pwd_comp_which.strip() == "":
        #    self.accounts.pwd_comp_which = "[Not provided]"
        self.sharing = TAQSharing(sharing)
        if self.sharing.phone_plan_admin == []:
            self.sharing.phone_plan_admin = ""
        self.smarthome = TAQSmarthome(smarthome)
        self.kids = TAQKids(kids)
        self.legal = TAQLegal(legal)

        self.generate_risk_reports()

    def generate_risk_reports(self):
        '''
        Generates all of the risk reports for the TAQ subforms.
        Gathers all risks together for the summary.
        '''
        self.all_risks = list()

        for obj in [self.devices, self.accounts, self.sharing, self.smarthome, self.kids]:
            risk_report: RiskReport = obj.generate_risk_report()
            self.all_risks.extend(risk_report.risk_details)

        return self.all_risks
