# pylint: disable=missing-module-docstring,missing-function-docstring

import logging
from os import path

from ..utils.yaml import yaml_load

logger = logging.getLogger(__name__)

PACKAGE_TYPE = 'installer'


def is_installer(filename):
    # NOTE: allow
    if not filename.endswith('.sh'):
        return False

    with open(filename) as file:  # pylint: disable=unspecified-encoding
        file.readline()
        cio_copyright = file.readline()
        # Copyright (c) 2012-2014 Continuum Analytics, Inc.

        # NOTE: it would be great if the installers had a unique identifier in the header

        # Made by CAS installer
        if 'CAS-INSTALLER' in cio_copyright:
            return True

        # miniconda installer
        if 'Copyright' not in cio_copyright or 'Continuum Analytics, Inc.' not in cio_copyright:
            return False

        return True


def inspect_package(filename, fileobj, *args, **kwarg):  # pylint: disable=unused-argument
    line = fileobj.readline()
    lines = []
    while line.startswith('#'):
        if ':' in line:
            lines.append(line.strip(' #\n'))
        line = fileobj.readline()

    try:
        installer_data = yaml_load('\n'.join(lines))
    finally:
        logger.error('Could not load installer info as YAML')

    summary = 'Conda installer for platform %s' % installer_data.pop('PLAT')
    name = installer_data.pop('NAME')
    version = installer_data.pop('VER')

    attrs = installer_data

    package_data = {
        'name': name,
        'summary': summary,
        'license': None,
    }
    release_data = {
        'version': version,
        'description': summary,
    }
    file_data = {
        'basename': path.basename(filename),
        'attrs': attrs,
        'binstar_package_type': 'file',
    }

    return package_data, release_data, file_data
