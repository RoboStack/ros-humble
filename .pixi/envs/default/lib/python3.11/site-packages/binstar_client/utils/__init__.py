# -*- coding: utf8 -*-
# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

from __future__ import annotations

import base64
import json
import logging
import sys
from hashlib import md5

# Re-export config
from .config import (
    get_server_api, dirs, load_token, store_token, remove_token, get_config, set_config, load_config, get_binstar,
    USER_CONFIG, USER_LOGDIR, SITE_CONFIG, DEFAULT_CONFIG
)
from .spec import PackageSpec, package_specs, parse_specs

logger = logging.getLogger('binstar')


def jencode(*E, **F):
    payload = dict(*E, **F)
    return json.dumps(payload), {'Content-Type': 'application/json'}


def compute_hash(file, buf_size=8192, size=None, hash_algorithm=md5):
    hash_obj = hash_algorithm()
    spos = file.tell()
    if size and size < buf_size:
        chunk = file.read(size)
    else:
        chunk = file.read(buf_size)
    while chunk:
        hash_obj.update(chunk)
        if size:
            size -= len(chunk)
            if size <= 0:
                break
        if size and size < buf_size:
            chunk = file.read(size)
        else:
            chunk = file.read(buf_size)
    hex_digest = hash_obj.hexdigest()

    base64_digest = base64.encodebytes(hash_obj.digest()).decode('ascii').rstrip('\n')

    # data_size based on bytes read.
    data_size = file.tell() - spos
    file.seek(spos)
    return (hex_digest, base64_digest, data_size)


def bool_input(prompt, default=True):
    default_str = '[Y|n]' if default else '[y|N]'
    while True:
        inpt = input('%s %s: ' % (prompt, default_str))
        if inpt.lower() in ['y', 'yes'] and not default:  # pylint: disable=no-else-return
            return True
        elif inpt.lower() in ['', 'n', 'no'] and not default:
            return False
        elif inpt.lower() in ['', 'y', 'yes']:
            return True
        elif inpt.lower() in ['n', 'no']:
            return False
        else:
            sys.stderr.write('please enter yes or no\n')


WAIT_SECONDS = 15
