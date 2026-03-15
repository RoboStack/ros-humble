# -*- coding: utf8 -*-

"""Utilities to manage file paths."""

from __future__ import annotations

__all__ = ['expandvars', 'normalize']

import os
import string
import typing

from . import conda


def expandvars(path: str) -> str:
    """
    Expand environment variables in :code:`path`.

    Missing conda-related variables might be injected from :data:`~binstar_client.utils.conda.CONDA_INFO`.
    """
    mapping: typing.Dict[str, str] = {
        **typing.cast(typing.Mapping[str, str], conda.CONDA_INFO),
        **os.environ,
    }
    return string.Template(path).safe_substitute(mapping)


def normalize(path: str) -> str:
    """Normalize file :code:`path`."""
    return os.path.abspath(os.path.expanduser(expandvars(path)))
