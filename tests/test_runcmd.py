"""catch_err turns a finished process into text; these pin what it returns."""

import subprocess
import sys

from phone_scanner import runcmd


def _proc(code, out="", err=""):
    script = f"import sys; sys.stdout.write({out!r}); sys.stderr.write({err!r}); sys.exit({code})"
    return subprocess.Popen(
        [sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


def test_output_of_a_successful_command_is_returned():
    assert runcmd.catch_err(_proc(0, out="hello world, this is fine\n")) == "hello world, this is fine\n"


def test_a_failing_command_returns_a_message_with_its_error():
    msg = runcmd.catch_err(_proc(2, err="boom"), cmd="thing", msg="context")
    assert "boom" in msg and "thing" in msg and "context" in msg


def test_a_short_output_that_says_error_is_treated_as_empty():
    assert runcmd.catch_err(_proc(0, out="error: no devices")) == ""


def test_a_permission_problem_gives_an_empty_result():
    p = _proc(1, err="insufficient permissions for device: user in plugdev group; are your udev rules wrong?")
    assert runcmd.catch_err(p) == ""


def test_large_output_is_read_fully():
    p = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 200000)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert runcmd.catch_err(p, large_output=True) == "x" * 200_000


def test_a_command_that_outlives_the_timeout_gives_an_empty_result():
    p = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert runcmd.catch_err(p, time=0.2) == ""
    finally:
        p.kill()


def test_run_command_fills_in_the_cli_name():
    p = runcmd.run_command("echo {cli}")
    assert p.stdout.read().decode().strip() == "adb"


def test_run_command_with_nowait_returns_a_pid():
    pid = runcmd.run_command("true", nowait=True)
    assert isinstance(pid, int)
