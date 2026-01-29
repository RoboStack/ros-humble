from errno import EACCES, EPERM
import os
import shutil
import stat
import sys

_quiet = False


def quiet(state=True):
    global _quiet
    _quiet = state


def _print_func(msg, end, file):
    global _quiet
    if not _quiet:
        print(msg, end=end, file=file)


def override_print(print_func=_print_func):
    global _print
    _print = print_func


_print = _print_func


def info(msg, end=None, file=None):
    global _print
    _print(msg, end=end, file=file)


def warning(msg, end=None, file=None):
    global _print
    _print(msg, end=end, file=file)


def error(msg, end=None, file=None):
    global _print
    file = sys.stderr if file is None else file
    _print(msg, end=end, file=file)


def rmtree(path):
    kwargs = {}
    if sys.platform == 'win32':
        kwargs['onerror'] = _onerror_windows
    return shutil.rmtree(path, **kwargs)


def _onerror_windows(function, path, excinfo):
    if isinstance(excinfo[1], OSError) and excinfo[1].errno in (EACCES, EPERM):
        os.chmod(path, stat.S_IWRITE)
        function(path)
