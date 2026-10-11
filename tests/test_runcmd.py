"""catch_err turns a finished process into text; these pin what it returns."""

import subprocess
import sys

import pytest

from phone_scanner import runcmd


def _proc(code, out="", err=""):
    script = f"import sys; sys.stdout.write({out!r}); sys.stderr.write({err!r}); sys.exit({code})"
    return subprocess.Popen(
        [sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


def test_output_of_a_successful_command_is_returned():
    assert runcmd.catch_err(_proc(0, out="hello world, this is fine\n")) == "hello world, this is fine\n"


def test_a_failing_command_returns_no_output_and_logs_its_error(monkeypatch):
    # One return type: the output, or "" when the command failed. The error
    # message used to be returned instead, and callers took it for output.
    logged = []
    monkeypatch.setattr(runcmd, "debug", lambda *a: logged.append(" ".join(map(str, a))))
    assert runcmd.catch_err(_proc(2, err="boom"), cmd="thing", msg="context") == ""
    assert any("boom" in m and "thing" in m and "context" in m for m in logged)


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


def test_run_command_takes_an_argument_list_and_does_not_use_a_shell():
    p = runcmd.run_command(["echo", "a;b $(id) `id` |c"])
    assert p.stdout.read().decode().strip() == "a;b $(id) `id` |c"


def test_run_command_rejects_a_string():
    with pytest.raises(TypeError):
        runcmd.run_command("echo hi")


def test_run_command_with_nowait_returns_a_pid():
    pid = runcmd.run_command(["true"], nowait=True)
    assert isinstance(pid, int)


def test_a_missing_program_looks_like_a_failed_process():
    p = runcmd.run_command(["definitely-not-installed-xyz", "--flag"])
    assert runcmd.catch_err(p, cmd="x") == ""
    assert p.returncode != 0


def test_run_checked_reports_success_and_output():
    ok, out = runcmd.run_checked([sys.executable, "-c", "print('Success')"])
    assert ok is True and out.strip() == "Success"


def test_run_checked_fails_on_a_nonzero_exit():
    ok, _ = runcmd.run_checked([sys.executable, "-c", "import sys; sys.exit(1)"])
    assert ok is False


@pytest.mark.parametrize("text", ["Failure [DELETE_FAILED_INTERNAL_ERROR]", "ERROR: Uninstall failed"])
def test_run_checked_fails_when_the_tool_says_so_but_exits_zero(text):
    ok, _ = runcmd.run_checked([sys.executable, "-c", f"print({text!r})"])
    assert ok is False


def test_run_checked_fails_for_a_missing_program():
    ok, _ = runcmd.run_checked(["definitely-not-installed-xyz"])
    assert ok is False


def test_run_checked_gives_up_after_the_timeout():
    ok, _ = runcmd.run_checked([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.3)
    assert ok is False
