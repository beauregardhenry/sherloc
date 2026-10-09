# import config
import io
import re
import shlex
import subprocess

"""
def add_to_error(*args):
    global ERROR_LOG
    m = '\n'.join(str(e) for e in args)
    print(m)
    ERROR_LOG.append(m)

def error():
    global ERROR_LOG
    e = ''
    if len(ERROR_LOG)>0:
        e, ERROR_LOG = ERROR_LOG[0], ERROR_LOG[1:]

        print("ERROR: {}".format(e))
    return e.replace("\n", "<br/>")
"""


# TODO: @sam the catch_err should only catch the os level errors, not
# application level errors. They should go to particular application specific
# handling.
def catch_err(
    p: subprocess.Popen[bytes], cmd="", msg="", time=5, large_output=False
) -> str:
    """TODO: Therer are two different types. homogenize them"""
    try:
        large_output_var = b""
        if large_output:
            if p.stdout:
                for line in p.stdout:
                    large_output_var += line

        p.wait(time)
        if p.returncode != 0:
            err_msg = (
                    "stderr was none. This may indicate large issues with process."
                )
            if p.stderr:
                err_msg = p.stderr.read().decode("utf-8")
                
            m = "[{}]: Error running {!r}. Error ({}): {}\n{}".format(
                "android", cmd, p.returncode, err_msg, msg
            )
            print(cmd, p.returncode, err_msg, msg)
            if "insufficient permissions for device: user in plugdev group" in err_msg:
                e = 'Error: Please set "USB For File Transfers" mode on your Android device.'
                print(e)
                return ""
            # config.add_to_error(m)
            return m
        else:
            if large_output:
                s = large_output_var.decode()
            else:
                if p.stdout:
                    s = p.stdout.read().decode()
                else:
                    return ""

            if (
                (len(s) <= 100 and re.search("(?i)(fail|error)", s))
                or "insufficient permissions for device: user in plugdev group; are your udev rules wrong?"
                in s
            ):
                # config.add_to_error(s)
                return ""
            if (
                "insufficient permissions for device: user in plugdev group; are your udev rules wrong?"
                in s
            ):
                print("Need USB for Charging.")
                return ""
            else:
                print(s)
                return s
    except Exception as ex:
        # config.add_to_error(ex)
        print("Exception>>>", ex)
        return ""


class _FailedProcess:
    """Looks like a finished `Popen` for a program that could not be started.

    A shell reports a missing program as exit status 127 with a message on
    stderr. Callers read `returncode`, `stdout` and `stderr`, so a program
    that cannot start looks the same.
    """

    returncode = 127
    pid = 0

    def __init__(self, args, error):
        self.args = args
        self.stdout = io.BytesIO(b"")
        self.stderr = io.BytesIO(f"{args[0]}: {error}".encode())

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        pass


def run_command(args, nowait=False):
    """Start a program and return the process (or its pid with `nowait`).

    `args` is the program and its arguments as a list. No shell is involved,
    so nothing in an argument can be interpreted as a command.
    """
    if isinstance(args, (str, bytes)):
        raise TypeError("run_command takes a list of arguments, not a string")
    args = [str(a) for a in args]
    print(" ".join(shlex.quote(a) for a in args))
    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as ex:
        p = _FailedProcess(args, ex)
    if nowait:
        return p.pid
    return p


_TOOL_SAID_NO = re.compile(r"(?im)^\s*(failure|error)\b")


def run_checked(args, timeout=30):
    """Run a program to completion. Returns `(succeeded, output)`.

    Some tools exit with status 0 and print `Failure [...]` or `ERROR: ...`.
    Those count as failures too.
    """
    if isinstance(args, (str, bytes)):
        raise TypeError("run_checked takes a list of arguments, not a string")
    args = [str(a) for a in args]
    try:
        done = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as ex:
        print("Could not run", args[0], "->", ex)
        return False, ""
    output = done.stdout + done.stderr
    return done.returncode == 0 and not _TOOL_SAID_NO.search(output), done.stdout
