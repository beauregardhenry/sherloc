# Importing each view module registers its routes; the names are re-exported.
# ruff: noqa: F401
from .index import index, get_device
from .consult import client_forms, edit_forms
from .scan import scan
from .instructions import instruction
from .control import killme
from .details import app_details
from .privacy import privacy, privacy_scan
from .save import delete_app
from .evidence import evidence_home, evidence_account, evidence_account_default, evidence_printout, evidence_taq, evidence_screenshots
from .evidence_scan import evidence_scan_start, evidence_scan_select, evidence_scan_investigate, evidence_scan_manualadd


