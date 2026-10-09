"""Stand-ins for device command line tools (adb, pymobiledevice3, ...).

A fake tool is a small script. It records the arguments it was called with
and prints the canned output whose `match` text appears in the joined
arguments. Tests can check both what the scanner parsed and exactly which
commands it ran, without a phone or a shell.

The canned output follows the documented format of each tool. It is not a
recording of a real device.
"""

import json
import stat
import sys
from pathlib import Path

_TEMPLATE = """#!{python}
import json, sys
base = {base!r}
argv = sys.argv[1:]
with open(base + ".calls", "a") as fh:
    fh.write(json.dumps(argv) + "\\n")
text = " ".join(argv)
for r in json.load(open(base + ".responses")):
    if r["match"] in text:
        sys.stdout.write(r.get("stdout", ""))
        sys.stderr.write(r.get("stderr", ""))
        sys.exit(r.get("rc", 0))
sys.exit(0)
"""


class FakeTool:
    def __init__(self, directory: Path, name: str, responses=None):
        self.path = Path(directory) / name
        base = str(self.path)
        self.path.write_text(_TEMPLATE.format(python=sys.executable, base=base))
        self.path.chmod(self.path.stat().st_mode | stat.S_IXUSR)
        self._calls = Path(base + ".calls")
        self._responses = Path(base + ".responses")
        self.respond(responses or [])

    def respond(self, responses):
        """Replace the canned responses: [{"match", "stdout", "stderr", "rc"}]."""
        self._responses.write_text(json.dumps(responses))

    @property
    def calls(self):
        """Argument lists of every call so far."""
        if not self._calls.exists():
            return []
        return [json.loads(line) for line in self._calls.read_text().splitlines()]
