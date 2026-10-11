"""evidence_model.py held 40 classes in 1,100 lines. They now live in modules
by domain, and `evidence_model` still exports every name it had.
"""

import importlib
from pathlib import Path

import pytest

import web  # noqa: F401  (import order: web first avoids a circular import)
import config
import evidence_model

LAYOUT = {
    "evidence_base": ["EvidenceDataEncoder", "Dictable", "DictInitClass",
                      "Risk", "RiskReport", "ScreenshotInfo", "Notes"],
    "evidence_accounts": ["AccountSection", "SuspiciousLogins", "PasswordCheck",
                          "RecoverySettings", "TwoFactorSettings", "SecurityQuestions",
                          "AccountInvestigation", "get_all_screenshot_files"],
    "evidence_apps": ["InstallInfo", "PermissionInfo", "AppInfo", "ScanData"],
    "evidence_taq": ["TAQDevices", "TAQAccounts", "TAQSharing", "TAQSmarthome",
                     "TAQKids", "TAQLegal", "TAQData"],
    "evidence_model": ["ConsultationData", "ConsultSetupData", "ConsultNotesData"],
}
CASES = [(m, n) for m, names in LAYOUT.items() for n in names]


@pytest.mark.parametrize("module,name", CASES)
def test_name_is_defined_in_its_domain_module(module, name):
    mod = importlib.import_module(module)
    assert getattr(mod, name).__module__ == module


@pytest.mark.parametrize("module,name", CASES)
def test_evidence_model_still_exports_every_name(module, name):
    assert getattr(evidence_model, name) is getattr(importlib.import_module(module), name)


@pytest.mark.parametrize("module", list(LAYOUT))
def test_module_is_under_400_lines(module):
    lines = (Path(config.THIS_DIR) / f"{module}.py").read_text().splitlines()
    assert len(lines) < 400, f"{module} has {len(lines)} lines"
