"""Turn the printout HTML into a PDF with WeasyPrint.

WeasyPrint has no JavaScript engine. It still loads images and stylesheets
that a page links to, including `file://` URLs and other websites, so every
fetch goes through `StaticOnlyFetcher`: only files under `webstatic/` (logos,
styles) and the screenshot folder (served by the app as `client-screenshots/`),
asked for by the app's own URL, are read from disk.
"""

import mimetypes
import os
from typing import Any
from urllib.parse import unquote, urlsplit

import weasyprint
from weasyprint.urls import URLFetcher, URLFetcherResponse

import config
from config import THIS_DIR

STATIC_ROOT = os.path.realpath(THIS_DIR / "webstatic")
ZOOM = 0.75

PAGE_CSS = """
/* Keep the page breaks the report had with wkhtmltopdf. The cover, the
   summary and every section are already followed by an empty `.pagebreak`
   div, so these other break rules would add blank pages. */
.cover-page, div.printout-summary { break-after: auto; }
div.new-page { break-before: auto; }
/* A section's last table is followed by a .pagebreak too. */
table.printout_columns:last-child { break-after: auto; }
@page {
  size: SIZE_W SIZE_H;
  margin: M_TOP M_SIDE M_BOTTOM M_SIDE;
  @bottom-center {
    content: "%s";
    font-family: Georgia, serif;
    font-size: FOOTER_PT;
  }
}
"""


class StaticOnlyFetcher(URLFetcher):
    """Serve the app's static files and client screenshots from disk; refuse the rest."""

    def __init__(self, url_root: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.url_root = url_root if url_root.endswith("/") else url_root + "/"

    def _folders(self) -> dict[str, str]:
        # The screenshot folder is read each time: it follows SHERLOC_DATA_DIR.
        return {
            "webstatic/": STATIC_ROOT,
            "client-screenshots/": os.path.realpath(config.SCREENSHOT_DIR),
        }

    def fetch(self, url: str, headers: Any = None) -> URLFetcherResponse:
        for url_prefix, root in self._folders().items():
            prefix = self.url_root + url_prefix
            if not url.startswith(prefix):
                continue
            rel = unquote(urlsplit(url).path[len(urlsplit(prefix).path):])
            path = os.path.realpath(os.path.join(root, rel))
            if not path.startswith(root + os.sep) or not os.path.isfile(path):
                break
            with open(path, "rb") as f:
                body = f.read()
            mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
            return URLFetcherResponse(url, body=body, headers={"Content-Type": mime})
        raise ValueError("Only the app's own static files and screenshots can be loaded.")


def _css_string(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render_pdf(html: str, *, url_root: str, footer: str) -> bytes:
    """Render `html` to PDF bytes. `footer` may use [page] and [toPage]."""
    footer_css = (
        '"' + _css_string(footer)
        .replace("[page]", '" counter(page) "')
        .replace("[toPage]", '" counter(pages) "') + '"'
    )
    # The page is laid out ZOOM times larger and shrunk to A4, as wkhtmltopdf's
    # default "smart shrinking" did, so text keeps the size clinics know.
    mm = lambda v: "%.1fmm" % (v / ZOOM)
    page_css = (
        PAGE_CSS.replace('"%s"', footer_css)
        .replace("SIZE_W", mm(210)).replace("SIZE_H", mm(297))
        .replace("FOOTER_PT", "%.1fpt" % (8 / ZOOM)).replace("M_TOP", mm(15)).replace("M_BOTTOM", mm(20)).replace("M_SIDE", mm(10))
    )
    fetcher = StaticOnlyFetcher(url_root)
    with open(os.path.join(STATIC_ROOT, "style.css")) as f:
        app_css = f.read()
    stylesheets = [
        weasyprint.CSS(string=app_css, url_fetcher=fetcher, base_url=url_root + "webstatic/"),
        weasyprint.CSS(string=page_css, url_fetcher=fetcher),
    ]
    doc = weasyprint.HTML(string=html, base_url=url_root, url_fetcher=fetcher)
    return doc.write_pdf(stylesheets=stylesheets, zoom=ZOOM)
