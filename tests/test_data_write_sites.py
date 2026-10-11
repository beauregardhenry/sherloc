"""Every place the app writes files or opens a database is on a reviewed list.

Client data must be removable. A new write site that nobody classified is
the most likely way for it to end up somewhere "Delete client data" does not
reach. This test fails on any unlisted site and says how to list it.

Each entry maps `file::function` to what is written:
  client-data  deleted by delete_client_data (or its folders)
  app-data     not client data (reference data, keys, logs of fixed text)
  tool         developer script or command line tool, not run by the web app
"""

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent / "sherloc"
LISTING = Path(__file__).with_name("data_write_sites.json")

WRITE_MODES = ("w", "a", "x", "+")
WRITE_ATTRS = {
    "write_text", "write_bytes", "mkdir", "makedirs", "to_csv", "to_json",
    "to_pickle", "to_excel", "copy", "copy2", "copyfile", "move", "mkdtemp",
    "RotatingFileHandler", "FileHandler", "FileLock", "connect", "fdopen",
    "NamedTemporaryFile", "TemporaryFile",
}
SKIP_PARTS = {"__pycache__", "static_data", "webstatic", "templates", "phone_dumps", "reports"}


def _mode_of(call):
    mode = None
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        mode = call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    return mode if isinstance(mode, str) else None


def _name(func):
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def find_sites():
    sites = set()
    for path in ROOT.rglob("*.py"):
        if SKIP_PARTS & set(path.relative_to(ROOT).parts):
            continue
        tree = ast.parse(path.read_text())
        rel = path.relative_to(ROOT).as_posix()

        class V(ast.NodeVisitor):
            def __init__(self):
                self.stack = []

            def visit_FunctionDef(self, node):
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                name = _name(node.func)
                hit = False
                if name == "open":
                    mode = _mode_of(node)
                    hit = bool(mode) and any(c in mode for c in WRITE_MODES)
                elif name in WRITE_ATTRS:
                    hit = True
                if hit:
                    where = ".".join(self.stack) or "<module>"
                    sites.add(f"{rel}::{where}::{name}")
                self.generic_visit(node)

        V().visit(tree)
    return sites


def test_every_write_site_is_listed():
    listed = set(json.loads(LISTING.read_text()))
    found = find_sites()
    unlisted = sorted(found - listed)
    assert not unlisted, (
        "New places that write files or open a database:\n  "
        + "\n  ".join(unlisted)
        + "\nDecide where the data goes and whether 'Delete client data' removes it, "
        "then add each to tests/data_write_sites.json with its kind."
    )


def test_listed_sites_still_exist():
    listed = json.loads(LISTING.read_text())
    gone = sorted(set(listed) - find_sites())
    assert not gone, "Remove from tests/data_write_sites.json: " + ", ".join(gone)


def test_every_entry_has_a_known_kind():
    listed = json.loads(LISTING.read_text())
    bad = {k: v for k, v in listed.items() if v not in {"client-data", "app-data", "tool"}}
    assert not bad
