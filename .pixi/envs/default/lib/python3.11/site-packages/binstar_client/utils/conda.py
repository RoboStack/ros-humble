# -*- coding: utf8 -*-

"""Utilities to detect :code:`conda`."""

from __future__ import annotations

__all__ = ['find_conda', 'CONDA_INFO']

import itertools

import json
import os
import subprocess  # nosec
import sys
import typing


FLAGS: typing.Final[int] = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0  # type: ignore


class CondaInfo(typing.TypedDict):
    """Details on detected conda instance."""
    # pylint: disable=invalid-name

    CONDA_EXE: str
    CONDA_PREFIX: str
    CONDA_ROOT: str


class Empty(typing.TypedDict):
    """
    Empty dictionary.

    Alternative to :class:`~CondaInfo` in case :code:`conda` is not found.
    """


def find_conda(*prefixes: str, use_env: bool = False) -> typing.Union[CondaInfo, Empty]:
    """
    Find :code:`conda` and collect essential details on it.

    :param prefixes: Extra prefixes where to look for conda.
    :param use_env: Use only existing environment variables if they contain all required details.

                    If at least one variable is missing - usual detection will be used.
    """
    commands: typing.List[str] = []
    command: str
    prefix: str
    root: str

    if command := os.environ.get('CONDA_EXE', ''):
        if use_env and (prefix := os.environ.get('CONDA_PREFIX', '')) and (root := os.environ.get('CONDA_ROOT', '')):
            return {'CONDA_EXE': command, 'CONDA_PREFIX': prefix, 'CONDA_ROOT': root}
        commands.append(command)

    prefix = os.path.abspath(sys.prefix)
    if os.name == 'nt':
        command = os.path.join('Scripts', 'conda-script.py')
    else:
        command = os.path.join('bin', 'conda')
    for prefix in itertools.chain(prefixes, [os.path.dirname(os.path.dirname(prefix)), prefix]):
        commands.append(os.path.join(prefix, command))

    commands.append('conda')

    for command in commands:
        info: typing.Mapping[str, typing.Any]
        try:
            info = json.loads(subprocess.check_output([command, 'info', '--json'], creationflags=FLAGS))  # nosec
            prefix = info.get('active_prefix', '') or info.get('conda_prefix', '')
            root = info.get('root_prefix', '') or info.get('conda_prefix', '')
        except (KeyError, OSError, ValueError, subprocess.SubprocessError):
            continue
        return {'CONDA_EXE': command, 'CONDA_PREFIX': prefix, 'CONDA_ROOT': root}

    return {}


CONDA_INFO: typing.Union[CondaInfo, Empty]

CONDA_EXE: typing.Optional[str]
CONDA_PREFIX: typing.Optional[str]
CONDA_ROOT: typing.Optional[str]


def __getattr__(name: str) -> typing.Any:
    """Calculate lazy module properties."""
    if name == 'CONDA_INFO':
        return globals().setdefault('CONDA_INFO', find_conda())

    if name in {'CONDA_EXE', 'CONDA_PREFIX', 'CONDA_ROOT'}:
        return sys.modules[__name__].CONDA_INFO.get(name, None)

    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
