"""A copy of the report that the client can take home.

It leaves out what names the clinic, the client or the device, and it can be
protected with a password. It is built in memory and sent straight to the
browser, so no copy of it is kept in the reports folder.
"""

import io
import secrets
import shutil
from typing import Optional

import pdfkit
import pypdf

import evidence_collection as ec
from config import THIS_DIR


def neutral_filename() -> str:
    """A file name that says nothing about the client, the clinic or the tool."""
    return f"notes-{secrets.token_hex(6)}.pdf"


def protect_pdf(data: bytes, password: Optional[str]) -> bytes:
    """Replace the file's metadata and, given a password, encrypt it with AES-256.

    wkhtmltopdf records its name, the Qt version and the creation time in the
    file. Those are replaced by a neutral title.
    """
    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(io.BytesIO(data)))
    writer.metadata = {"/Title": "Notes"}
    if password:
        writer.encrypt(password, algorithm="AES-256")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def create_takehome_pdf(context: dict, password: Optional[str] = None) -> bytes:
    """Render the take-home copy and return the PDF bytes."""
    context = dict(context, takehome=True)
    html = ec.render_printout_html(context)
    wkhtmltopdf = shutil.which("wkhtmltopdf") or "/usr/local/bin/wkhtmltopdf"
    conf = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf)
    css = str(THIS_DIR / "webstatic" / "style.css")
    data = pdfkit.from_string(
        html, False, options=ec.printout_pdf_options(takehome=True), configuration=conf, css=css
    )
    return protect_pdf(data, password)
