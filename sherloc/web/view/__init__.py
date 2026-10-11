# Importing each view module registers its routes; the names are re-exported.
# ruff: noqa: F401
from .consult import client_forms, edit_forms
from .control import killme
from .details import app_details
from .evidence import (
    evidence_account,
    evidence_account_default,
    evidence_home,
    evidence_printout,
    evidence_screenshots,
    evidence_taq,
)
from .evidence_scan import (
    evidence_scan_investigate,
    evidence_scan_manualadd,
    evidence_scan_select,
    evidence_scan_start,
)
from .index import get_device, index
from .instructions import instruction
from .privacy import privacy, privacy_scan
from .save import delete_app
from .scan import scan


