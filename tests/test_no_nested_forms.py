"""Browsers drop a <form> that sits inside another <form>.

The "Delete Client Data" button on the evidence home page was such a form.
The browser ignored it, so a click submitted the notes form instead and
nothing was deleted, with no confirmation shown. Tests that post to the route
directly could not see this.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

import config

TEMPLATES = sorted((Path(config.THIS_DIR) / "templates").glob("*.html"))


class _Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nested = 0
        self.buttons = []  # (attrs, inside_form)

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            if self.depth:
                self.nested += 1
            self.depth += 1
        elif tag == "button":
            self.buttons.append((dict(attrs), self.depth > 0))

    def handle_endtag(self, tag):
        if tag == "form" and self.depth:
            self.depth -= 1


def _strip_jinja(text):
    return re.sub(r"\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}", "", text, flags=re.S)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.name)
def test_template_has_no_form_inside_a_form(path):
    p = _Forms()
    p.feed(_strip_jinja(path.read_text()))
    assert p.nested == 0, f"{path.name}: {p.nested} <form> nested in another <form>"


def test_the_delete_buttons_on_the_home_page_ask_first_and_post_to_their_own_route():
    text = (Path(config.THIS_DIR) / "templates" / "evidence-home.html").read_text()
    buttons = re.findall(r"<button[^>]*>\s*(?:Delete Client Data|Delete)\s*</button>", text)
    assert len(buttons) == 3
    for b in buttons:
        assert "formaction=" in b and 'formmethod="post"' in b
        assert "confirm(" in b
