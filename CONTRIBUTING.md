# Contributing to Sherloc

Sherloc handles evidence from people in abuse situations. Read "What to protect" before you change code that touches client data.

## Set up

You need Python 3.12 or newer. You do not need root.

```bash
./dev.sh            # first run creates .venv, installs everything, runs the tests
./dev.sh -- -k name # run part of the suite
```

`adb` and `ideviceinstaller` are optional for development. The PDF tests need Pango (see the README) and use `pdftotext` (poppler) when it is installed. No test needs a phone: device tools are replaced by fake programs (`tests/fakebin.py`).

### Developing on an Intel Mac

Intel Macs can be used for development but not to run consultations (the README lists the supported computers). Homebrew treats Intel Macs as a Tier 3 configuration and often cannot build Pango or `ideviceinstaller`, so skip `brew bundle` and install only Python:

```bash
brew install python@3.12
./dev.sh
```

Without Pango, the app still runs and the tests that make a PDF are skipped, each with the reason. Asking the app for a report shows a message instead of a PDF. CI has Pango and sets `SHERLOC_REQUIRE_PDF=1`, so every pull request still runs the PDF tests. Set the same variable locally to make a missing Pango an error instead of a skip.

To run the app itself, see the README.

## Before you open a pull request

- Run `./dev.sh`. The suite includes checks that fail on:
  - a new undefined name, bare `except`, mutable default argument, `eval` or `shell=True`, or dead code: an unused import or variable, or commented-out code. Delete code instead of commenting it out; git keeps the history (`tests/test_lint_ratchet.py`; existing findings are listed in `tests/lint_baseline.json`, which should only get shorter)
  - unsorted imports. `ruff check --select I001 --fix sherloc tests` sorts them (`tests/test_import_order.py`)
  - a place that writes a file or opens a database and is not listed in `tests/data_write_sites.json`
  - a public name removed from `evidence_collection`
  - a changed URL (`tests/routes_snapshot.txt`)
  - coverage below the floor set in `.github/workflows/tests.yml`
- Write the test first and watch it fail. Then make it pass.
- A change to a page should keep `tests/test_browser_smoke.py` passing. It clicks through the evidence home page in Chromium and runs when Playwright is installed (`pip install playwright` and `python -m playwright install chromium`); CI always runs it.
- Keep one theme per pull request.
- Add a line to `CHANGELOG.md` under "Unreleased".
- Modules listed in `tests/test_typed_modules.py` are checked with mypy. Annotate new modules and add them there.

## What to protect

- Use no real client data in tests, fixtures, issues or screenshots.
- Do not print client data (notes, names, serials, app lists). Use `debuglog.debug`; it prints only with `DEBUG=1`. Use `debuglog.warn` only for fixed messages.
- Run device tools with an argument list, never a shell string. Validate serials and app ids with `inputcheck` before they reach a command or a path.
- Anything that stores client data must live in a folder that "Delete client data" empties, and must be added to `tests/data_write_sites.json`.
- Canned device output in tests must follow the tool's documented format. Say in the test if it was not recorded from a real device.

## Reporting a security problem

Do not open a public issue. See [SECURITY.md](SECURITY.md).

## Other questions

Open an issue. Include your operating system, Python version and the steps that reproduce the problem. Leave out anything that identifies a client.
