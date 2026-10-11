"""Base classes and small shared types for the consultation data."""
from pathlib import Path
import json
import subprocess


# Helps create JSON encoding from nested classes
class EvidenceDataEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        return o.__dict__


class Dictable:
    def to_dict(self):
        return json.loads(json.dumps(self, cls=EvidenceDataEncoder))


# Base class for nested classes where we'll input data as dict (for ease)
class DictInitClass(Dictable):
    attrs = []

    def __init__(self, datadict=None):
        if datadict is None:
            datadict = dict()
        for k in self.attrs:
            if k in list(datadict.keys()):
                setattr(self, k, datadict[k])
            else:
                setattr(self, k, "")


class Risk(Dictable):
    def __init__(self,
                 risk="",
                 description=""):
        self.risk = risk
        self.description = description


class RiskReport(Dictable):
    def __init__(self,
                 risk_details=None):
        if risk_details is None:
            risk_details = list()
        self.risk_details = risk_details
        self.risk_present = len(risk_details) > 0


class Notes(DictInitClass):
    attrs = ['client_notes', 'consultant_notes']


class ScreenshotInfo(Dictable):
    def __init__(self,
                 fname="",
                 context="",  # root, account, or app
                 device_nickname=None,
                 device_serial=None,
                 app_id=None,
                 app_name=None,
                 username=None,
                 account_section=None,
                 get_metadata=True):
        self.fname = fname
        self.context = context

        # For root and app screenshots
        self.device_nickname = device_nickname
        self.device_serial = device_serial

        # Just for app screenshots
        self.app_id = app_id
        self.app_name = app_name

        # Just for account screenshots
        self.username = username
        self.account_section = account_section

        self.metadata = dict()
        if get_metadata:
            self.get_metadata()

    def get_metadata(self):
        """
        Uses exiftool (bash) to get metadata for our PNG screenshots.
        Available metadata:
            - ExifToolVersion
            - FileName
            - Directory
            - FileSize
            - FileModifyDate
            - FileAccessDate
            - FileInodeChangeDate
            - FilePermissions
            - FileType
            - FileTypeExtension
            - MIMEType
            - ImageWidth
            - ImageHeight
            - BitDepth
            - ColorType
            - Compression
            - Filter
            - Interlace
            - SRGBRendering
            - SignificantBits
            - ImageSize
            - Megapixels
        """

        data_to_get = ["FileModifyDate",
                       "FileAccessDate",]

        self.metadata = dict()

        for item in data_to_get:
            result = subprocess.run(
                ["exiftool", "-" + item, self.fname],
                capture_output=True, text=True
            )
            data = result.stdout.split(":", 1)[-1].strip()
            self.metadata[item] = data

        return self.metadata
