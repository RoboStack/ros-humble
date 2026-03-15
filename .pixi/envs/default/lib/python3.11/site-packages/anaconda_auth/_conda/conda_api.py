# This is a minimal reimplementation of the deprecated conda.cli.python_api
# module. It uses the subprocess module to duplicate the fullest extent of
# the run_command functionality needed for tests. But most of the internal
# uses of run_command do not require this overhead and are better served
# working in process. So when subprocess is needed, we do this:
#   from anaconda_auth._conda.conda_api import Commands, run_command
# and when it is not needed, we do this:
#   from anaconda_auth._conda.conda_api import Commands
#   from conda.cli.main import main as run_command


import subprocess


class Commands:
    CLEAN = "clean"
    CONFIG = "config"
    INSTALL = "install"
    LIST = "list"
    REMOVE = "remove"
    SEARCH = "search"


def run_command(*args, use_exception_handler=False):  # type: ignore
    args = ("python", "-m", "conda") + args
    proc = subprocess.run(args, capture_output=True, text=True)
    return proc.stdout, proc.stderr, proc.returncode
