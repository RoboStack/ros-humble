# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

from __future__ import annotations, print_function

import json
import os.path
import re
import sys
from pprint import pprint
from typing import Any

from conda_package_streaming.package_streaming import (
    CondaComponent,
    stream_conda_component,
)

from ..utils.notebook.data_uri import data_uri_from_bytes

os_map = {'osx': 'darwin', 'win': 'win32'}
specs_re = re.compile('^([=><]+)(.*)$')


def transform_conda_deps(deps):
    """
    Format dependencies into a common binstar format
    """
    depends = []
    for dep in deps:
        dep = dep.strip()
        name_spec = dep.split(' ', 1)
        if len(name_spec) == 1:
            (name,) = name_spec
            depends.append({'name': name, 'specs': []})
        elif len(name_spec) == 2:
            name, spec = name_spec
            if spec.endswith('*'):  # Star does nothing in semver
                spec = spec[:-1]

            match = specs_re.match(spec)
            if match:
                operator, spec = match.groups()
            else:
                operator = '=='

            depends.append({'name': name, 'specs': [[operator, spec]]})
        elif len(name_spec) == 3:
            name, spec, build_str = name_spec
            if spec.endswith('*'):  # Star does nothing in semver
                spec = spec[:-1]

            match = specs_re.match(spec)
            if match:
                operator, spec = match.groups()
            else:
                operator = '=='

            depends.append(
                {'name': name, 'specs': [['==', '%s+%s' % (spec, build_str)]]}
            )

    return {'depends': depends}


def get_subdir(index):
    """
    Return the sub-directory given the index dictionary.  The return
    value is obtained in the following order:

    1. when the 'subdir' key exists, it's value is returned
    2. if the 'arch' is None, or does not exist, 'noarch' is returned
    3. otherwise, the return value is constructed from the 'platform' key
       and the 'arch' key (where 'x86' is replaced by '32',
       and 'x86_64' by '64')
    """
    try:
        return index['subdir']
    except KeyError:
        arch = index.get('arch')
        if arch is None:
            return 'noarch'
        intel_map = {'x86': '32', 'x86_64': '64'}
        return '%s-%s' % (index.get('platform'), intel_map.get(arch, arch))


def inspect_conda_info_dir(info_contents: dict[str, bytes], basename: str) -> tuple[dict, dict, dict]:
    # pylint: disable=too-many-locals
    def _load(filename, default=None):
        info_path = f'info/{filename}'
        if info_path in info_contents:
            return json.loads(info_contents[info_path])
        return default

    index = _load('index.json', None)
    if index is None:
        raise TypeError('info/index.json required in conda package')

    recipe = _load('recipe.json')
    about = recipe.get('about', {}) if recipe else _load('about.json', {})
    has_prefix = 'info/has_prefix' in info_contents

    # Load icon defined in the index.json and file exists inside info folder
    icon_b64 = index.get('icon', None)
    if index.get('icon'):
        for icon_key in (f'info/{index.get("icon", None)}', 'info/icon.png'):
            if icon_key in info_contents:
                icon_b64 = data_uri_from_bytes(info_contents[icon_key])
                break

    subdir = get_subdir(index)
    machine = index.get('arch', None)
    platform = index.get('platform', None)

    operatingsystem = os_map.get(platform, platform)

    package_data = {
        'name': index.pop('name'),
        # NOTE: this info should be removed and moved to release
        'summary': about.get('summary', ''),
        'description': about.get('description', ''),
        'license': about.get('license'),
        'license_url': about.get('license_url'),
        'license_family': about.get('license_family'),
        'dev_url': about.get('dev_url'),
        'doc_url': about.get('doc_url'),
        'home': about.get('home'),
        'source_git_url': about.get('source_git_url'),
    }
    release_data = {
        'version': index.pop('version'),
        'home_page': about.get('home'),
        'description': about.get('description', ''),
        'summary': about.get('summary', ''),
        'dev_url': about.get('dev_url'),
        'doc_url': about.get('doc_url'),
        'home': about.get('home'),
        'source_git_url': about.get('source_git_url'),
        'source_git_tag': about.get('source_git_tag'),
        'icon': icon_b64,
        'license': about.get('license'),
        'license_url': about.get('license_url'),
        'license_family': about.get('license_family'),
    }
    file_data: dict[str, Any] = {
        'basename': '%s/%s' % (subdir, basename),
        'attrs': {
            'operatingsystem': operatingsystem,
            'machine': machine,
            'target-triplet': '%s-any-%s' % (machine, operatingsystem),
            'has_prefix': has_prefix,
            'subdir': subdir,
        }
    }

    file_data['attrs'].update(index)
    conda_depends = index.get('depends', index.get('requires', []))
    file_data['dependencies'] = transform_conda_deps(conda_depends)

    return package_data, release_data, file_data


def gather_info_dir(
    path: os.PathLike,
    wanted: frozenset[str] = frozenset(
        (
            'info/index.json',
            'info/recipe.json',
            'info/about.json',
            'info/has_prefix',
        )
    ),
) -> dict[str, bytes]:
    """Use conda-package-streaming to gather files without extracting to disk."""
    # based on code from conda-index
    have: dict[str, bytes] = {}
    seeking = set(wanted)
    with open(path, mode='rb') as fileobj:
        package_stream = stream_conda_component(
            path, fileobj, CondaComponent.info
        )
        for tar, member in package_stream:
            if member.name in wanted:
                seeking.remove(member.name)
                reader = tar.extractfile(member)
                if reader is None:
                    continue
                have[member.name] = reader.read()

            if not seeking:  # we got what we wanted
                package_stream.close()

    # extremely rare icon case. index.json lists a <hash>.png but the icon
    # appears to always be info/icon.png.
    if b'"icon"' in have.get('info/index.json', b''):
        index_json = json.loads(have['info/index.json'])
        # this case matters for our unit tests
        wanted = frozenset(('info/icon.png', f'info/{index_json["icon"]}'))
        have.update(gather_info_dir(path, wanted=wanted))

    return have


def inspect_conda_package(filename, *args, **kwargs):  # pylint: disable=unused-argument
    info_contents = gather_info_dir(filename)
    package_data, release_data, file_data = inspect_conda_info_dir(
        info_contents, os.path.basename(filename)
    )
    return package_data, release_data, file_data


def main():
    filename = sys.argv[1]
    package_data, release_data, file_data = inspect_conda_package(filename)
    pprint(package_data)
    print('--')
    pprint(release_data)
    print('--')
    pprint(file_data)


if __name__ == '__main__':
    main()
