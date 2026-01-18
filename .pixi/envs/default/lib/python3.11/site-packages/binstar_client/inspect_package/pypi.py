# pylint: disable=consider-using-with,unused-argument,import-outside-toplevel,unspecified-encoding
# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

from __future__ import print_function, unicode_literals

import json
import re
import sys
import tarfile
import zipfile
from email.parser import Parser
from os import path

import pkg_resources

from binstar_client import errors
from binstar_client.inspect_package.uitls import extract_first, pop_key
from binstar_client.utils.config import PackageType


def sort_ver(item):
    return item[1]


def sort_key(item):
    return item['name']


# Helper methods for parsing requirements for latest metadata style
# -----------------------------------------------------------------------------

# This regex can process requirement including or not including name.
# This is useful for parsing, for example, `Python-Version`
PARTIAL_PYPI_SPEC_PATTERN = re.compile(r'''
    # Text needs to be stripped and all extra spaces replaced by single spaces
    (?P<name>^[A-Z0-9][A-Z0-9._-]*)?
    \s?
    (\[(?P<extras>.*)\])?
    \s?
    (?P<constraints>\(? \s? ([\w\d<>=!~,\s\.\*]*) \s? \)? )?
    \s?
''', re.VERBOSE | re.IGNORECASE)


def norm_package_name(name):
    return name.replace('.', '-').replace('_', '-').lower() if name else ''


def norm_package_version(version):
    """Normalize a version by removing extra spaces and parentheses."""
    if version:
        version = ''.join(version.split())
        if version.startswith('(') and version.endswith(')'):
            version = version[1:-1]
    else:
        version = ''

    return version


def split_spec(spec, sep):
    """Split a spec by separator and return stripped start and end parts."""
    parts = spec.rsplit(sep, 1)
    spec_start = parts[0].strip()
    spec_end = ''
    if len(parts) == 2:
        spec_end = parts[-1].strip()
    return spec_start, spec_end


def parse_specification(spec):
    """
    Parse a requirement from a python distribution metadata and return a
    tuple with name, extras, constraints, marker and url components.

    This method does not enforce strict specifications but extracts the
    information which is assumed to be *correct*. As such no errors are raised.

    Example
    -------
    spec = 'requests[security, tests] >=3.3.0 ; foo >= 2.7 or bar == 1'

    ('requests', ['security', 'pyfoo'], '>=3.3.0', 'foo >= 2.7 or bar == 1', '')
    """
    name, extras, const = spec, [], ''

    # Remove excess whitespace
    spec = ' '.join(part for part in spec.split(' ') if part).strip()

    # Extract marker (Assumes that there can only be one ';' inside the spec)
    spec, marker = split_spec(spec, ';')

    # Extract url (Assumes that there can only be one '@' inside the spec)
    spec, url = split_spec(spec, '@')

    # Find name, extras and constraints
    r = PARTIAL_PYPI_SPEC_PATTERN.match(spec)
    if r:
        # Normalize name
        name = r.group('name')

        # Clean extras
        extras = r.group('extras')
        extras = [extra.strip() for extra in extras.split(',') if extra] if extras else []

        # Clean constraints
        const = r.group('constraints')
        const = ''.join(part for part in const.split(' ') if part).strip()
        if const.startswith('(') and const.endswith(')'):
            # Remove parens
            const = const[1:-1]

    return name, extras, const, marker, url


def get_header_description(filedata):
    """Get description from metadata file and remove any empty lines at end."""
    python_version = sys.version_info.major
    if python_version == 3:
        filedata = Parser().parsestr(filedata)
    else:
        filedata = Parser().parsestr(filedata.encode('UTF-8', 'replace'))

    payload = filedata.get_payload()
    lines = payload.split('\n')
    while True:
        if lines and lines[-1] == '':
            lines.pop()
        else:
            break
    return '\n'.join(lines)


# Original helper functions
# -----------------------------------------------------------------------------
def python_version_check(filedata):
    python_version = sys.version_info.major

    if python_version == 3:
        filedata = Parser().parsestr(filedata).items()
    else:
        filedata = Parser().parsestr(filedata.encode('UTF-8', 'replace')).items()

    return filedata


def parse_requirement(line, deps, extras, extra):
    req = pkg_resources.Requirement.parse(line)
    req.specs.sort(key=sort_ver)
    if extra:
        extras[extra].append({'name': req.key, 'specs': req.specs or []})
    else:
        deps.append({'name': req.key, 'specs': req.specs or []})

    deps.sort(key=sort_key)
    for extra_item in extras.values():
        extra_item.sort(key=sort_key)


def parse_requires_txt(requires_txt):
    deps = []
    error = False
    extras = {}
    extra = None

    for line in requires_txt.split('\n'):
        line = line.strip()

        if not line:
            continue

        if line.startswith('[') and line.endswith(']'):
            extra = line[1:-1]
            extras.setdefault(extra, [])
            # Dont parse this requirement
            continue
        try:
            parse_requirement(line, deps, extras, extra)
        except ValueError:
            error = True

    extras = [
        {
            'name': key,
            'depends': sorted(value, key=sort_key),
        }
        for key, value in extras.items()
    ]

    return {
        'has_dep_errors': error,
        'depends': sorted(deps, key=sort_key),
        'extras': sorted(extras, key=sort_key),
    }


def format_requirements(requires):
    obj = []
    for req in requires:
        req = req.strip()

        # Get environment marker
        marker = None
        if ';' in req:
            req, marker = req.split(';', 1)
            marker = marker.strip()
        else:
            marker = None

        req_spec = req.split(' ', 1)
        if len(req_spec) == 1:
            # Note: req.lower() was introduced here to enforce the same parsing
            # using metadata.json and METADATA
            obj.append({'name': req.lower(), 'specs': []})
        else:
            req, spec = req_spec
            spec = spec.strip()

            if spec[0] == '(':
                spec = spec[1:]

            if spec[-1] == ')':
                spec = spec[:-1]

            req = pkg_resources.Requirement.parse('%s %s' % (req, spec))
            req.specs.sort(key=sort_ver)
            obj.append({
                'name': req.key,
                'specs': req.specs or [],
            })
    return obj


def format_run_requires_metadata(run_requires):
    deps = []
    extras = []
    environments = []
    for run_require in run_requires:
        extra = run_require.get('extra')
        env = run_require.get('environment')
        requires = run_require['requires']

        if env:
            obj = []
            environments.append({'name': env, 'depends': obj})
        elif extra is None:
            obj = deps
        else:
            obj = []
            extras.append({'name': extra, 'depends': obj})

        obj.extend(format_requirements(requires))
        print(obj)

    deps.sort(key=sort_key)
    extras.sort(key=sort_key)
    for extra in extras:
        extra['depends'].sort(key=sort_key)

    attrs = {
        'has_dep_errors': False,
        'depends': sorted(deps, key=sort_key),
        'extras': extras,
        'environments': environments
    }

    return attrs


def format_requires_metadata(run_requires):
    deps = []
    extras = []

    extras_re = re.compile('extra == [\'\'](.*)[\'\']')
    has_dep_errors = False

    if not isinstance(run_requires, dict):
        has_dep_errors = True
        run_requires = {}

    for key, requirements in run_requires.items():
        is_extra = extras_re.match(key)
        if is_extra:
            extra = is_extra.groups()[0]
            if extra is None:
                obj = deps
            else:
                obj = []
                extras.append({'name': extra, 'depends': obj})

        else:
            obj = deps

        obj.extend(format_requirements(requirements))

    attrs = {
        'has_dep_errors': has_dep_errors,
        'depends': deps,
        'extra_depends': extras
    }

    return attrs


def format_sdist_header_metadata(data, filename):  # pylint: disable=too-many-branches,too-many-locals
    """
    Format the metadata of Standard Python packages stored in email header format.

    Currently only used as backup on the wheel (compressed) file format.
    """
    description = get_header_description(data)
    config_items = python_version_check(data)
    attrs = dict(config_items)
    name = pop_key(attrs, 'Name', None)

    basename = path.basename(filename)
    if name is None:
        name = basename.split('-')[0]

    package_data = {
        'name': name,
        'summary': pop_key(attrs, 'Summary', None),
        'license': pop_key(attrs, 'License', None),
    }

    release_data = {
        'version': pop_key(attrs, 'Version'),
        'description': pop_key(attrs, 'Description', description),
        'home_page': pop_key(attrs, 'Home-page', None),
    }

    file_data = {
        'basename': basename,
        'attrs': {
            'packagetype': 'sdist',
            'python_version': 'source',
        }
    }

    # Parse multiple keys
    deps = []
    exts = {}
    environments = {}
    for key, val in config_items:
        if key in ['Requires-Dist', 'Requires']:
            name, extras, const, marker, url = parse_specification(val)  # pylint: disable=unused-variable
            name = norm_package_name(name)
            specs = const.split(',')
            new_specs = []
            for spec in specs:
                pos = [index for index, character in enumerate(spec) if character in '0123456789']
                if pos:
                    pos = pos[0]
                    comp, spec_ = spec[:pos].strip(), spec[pos:].strip()
                    new_specs.append((comp, spec_))

            # NOTE: All this is to preserve the format used originally
            # but is this really needed?
            if marker:
                if marker.startswith('extra'):
                    marker = marker.replace('extra', '')
                    marker = marker.replace('==', '').strip()
                    ext = marker.rsplit(' ')[-1]
                    if ext.startswith(('"', '\'')) and ext.endswith(('"', '\'')):
                        ext = ext[1:-1]

                    if ext not in exts:
                        exts[ext] = [{'name': name, 'specs': new_specs}]
                    else:
                        exts[ext].append({'name': name, 'specs': new_specs})
                else:
                    if marker not in environments:
                        environments[marker] = [{'name': name, 'specs': new_specs}]
                    else:
                        environments[marker].append({'name': name, 'specs': new_specs})
            else:
                deps.append({
                    'name': name,
                    'specs': new_specs,
                })

    deps.sort(key=lambda o: o['name'])

    new_exts = []
    for key, values in exts.items():
        new_exts.append({'name': key, 'depends': values})

    new_environments = []
    for key, values in environments.items():
        new_environments.append({'name': key, 'depends': values})

    file_data.update(dependencies={
        'has_dep_errors': False,
        'depends': deps,
        'extras': new_exts,
        'environments': new_environments,
    })

    return package_data, release_data, file_data


def format_wheel_json_metadata(data, filename, zip_file):
    package_data = {
        'name': pop_key(data, 'name'),
        'summary': pop_key(data, 'summary', None),
        'license': pop_key(data, 'license', None),
    }
    description_doc = (data.get('document_names') or {}).get('description')

    # Metadata version 2.0
    if not description_doc:
        description_doc = data.get('extensions', {}).get(
            'python.details', {}).get('document_names', {}).get('description')

    if description_doc:
        description = extract_first(zip_file, '*.dist-info/%s' % description_doc).strip()
    else:
        description = None

    home_page = (data.get('project_urls', {})).get('Home')
    if not home_page:
        home_page = data.get('extensions', {}).get('python.details', {}).get('project_urls', {}).get('Home')

    release_data = {
        'version': pop_key(data, 'version'),
        'description': description,
        'home_page': home_page,
    }

    attrs = {
        'packagetype': 'bdist_wheel',
        'python_version': 'source',
        'pypi': [
            {
                'key': key,
                'value': value,
            }
            for key, value in data.items()
        ],
    }

    if data.get('run_requires', {}):
        dependencies = format_run_requires_metadata(data['run_requires'])
    else:
        dependencies = format_requires_metadata(data.get('requires', {}))

    file_data = {
        'basename': path.basename(filename),
        'attrs': attrs,
        'dependencies': dependencies,
    }

    return package_data, release_data, file_data


def inspect_pypi_package_whl(filename, fileobj):
    tar_file = zipfile.ZipFile(fileobj)

    json_data = extract_first(tar_file, '*.dist-info/metadata.json')
    if json_data is None:
        json_data = extract_first(tar_file, '*.dist-info/pydist.json')

    # Metadata 2.1 removed metatada.json. Using good old distutils as fallback
    data = None
    data = extract_first(tar_file, '*.dist-info/METADATA')

    if json_data:
        package_data, release_data, file_data = format_wheel_json_metadata(json.loads(
            json_data), filename, tar_file)
    elif data:
        # Metadata 2.1 removed metatada.json
        package_data, release_data, file_data = format_sdist_header_metadata(data, filename)
    else:
        package_data, release_data, file_data = {}, {}, {}

    filename = path.basename(filename)
    file_components = filename[:-4].split('-')

    if len(file_components) == 5:
        _, _, python_version, abi, platform = file_components
        build_no = 0
    elif len(file_components) == 6:
        _, _, build_no, python_version, abi, platform = file_components
    else:
        raise TypeError('Bad wheel package name')

    if platform == 'any':
        platform = None

    if abi == 'none':
        abi = None

    file_data.setdefault('attrs', {})

    file_data['attrs'] = {
        'build_no': build_no,
        'python_version': python_version,
        'abi': abi,
        'packagetype': 'bdist_wheel',
    }

    file_data.update(platform=platform)
    return package_data, release_data, file_data


def disutils_dependencies(config_items):
    # NOTE: This is not handling environment markers or extras!
    requirements = [
        value
        for key, value in config_items
        if key in ['Requires-Dist', 'Requires']
    ]
    depends = format_requirements(requirements)

    return {
        'depends': depends,
        'extras': [],
        'has_dep_errors': False
    }


def inspect_pypi_package_sdist(filename, fileobj):
    tar_file = tarfile.open(filename, fileobj=fileobj)

    data = extract_first(tar_file, '*.egg-info/PKG-INFO')

    distribute = False
    if data is None:
        data = extract_first(tar_file, '*/PKG-INFO')
        distribute = True
        if data is None:
            raise errors.NoMetadataError(
                'Could not find *.egg-info/PKG-INFO file in {} sdist'.format(PackageType.STANDARD_PYTHON.label))
    config_items = python_version_check(data)
    attrs = dict(config_items)
    name = pop_key(attrs, 'Name', None)

    if name is None:
        basename = path.basename(filename)
        name = basename.split('-')[0]

    package_data = {
        'name': name,
        'summary': pop_key(attrs, 'Summary', None),
        'license': pop_key(attrs, 'License', None),
    }

    release_data = {
        'version': pop_key(attrs, 'Version'),
        'description': pop_key(attrs, 'Description', None),
        'home_page': pop_key(attrs, 'Home-page', None),
    }

    file_data = {
        'basename': path.basename(filename),
        'attrs': {
            'packagetype': 'sdist',
            'python_version': 'source',
        },
    }

    if distribute:  # Distribute does not create dep files
        file_data.update(dependencies=disutils_dependencies(config_items))

    requires_txt = extract_first(tar_file, '*.egg-info/requires.txt')
    if requires_txt:
        file_data.update(dependencies=parse_requires_txt(requires_txt))

    return package_data, release_data, file_data


def inspect_pypi_package_egg(filename, fileobj):
    tar_file = zipfile.ZipFile(fileobj)

    data = extract_first(tar_file, 'EGG-INFO/PKG-INFO')
    if data is None:
        raise errors.NoMetadataError(
            'Could not find EGG-INFO/PKG-INFO file in {} sdist'.format(PackageType.STANDARD_PYTHON.label))
    attrs = dict(python_version_check(data))

    package_data = {'name': pop_key(attrs, 'Name'),
                    'summary': pop_key(attrs, 'Summary', None),
                    'license': pop_key(attrs, 'License', None)}

    release_data = {'version': pop_key(attrs, 'Version'),
                    'description': pop_key(attrs, 'Description', None),
                    'home_page': pop_key(attrs, 'Home-page', None)}

    basename = path.basename(filename)
    if len(basename.split('-')) == 4:
        _, _, python_version, platform = basename[:-4].split('-')
    else:
        python_version = 'source'
        platform = None

    file_data = {'basename': path.basename(filename),
                 'attrs': {'packagetype': 'bdist_egg',
                           'python_version': python_version},
                 'platform': platform}

    requires_txt = extract_first(tar_file, 'EGG-INFO/requires.txt')
    if requires_txt:
        file_data.update(dependencies=parse_requires_txt(requires_txt))

    return package_data, release_data, file_data


def inspect_pypi_package_zip(filename, fileobj):
    tar_file = zipfile.ZipFile(fileobj)

    data = extract_first(tar_file, '*/PKG-INFO')
    if data is None:
        raise errors.NoMetadataError(
            'Could not find EGG-INFO/PKG-INFO file in {} sdist'.format(PackageType.STANDARD_PYTHON.label))

    attrs = dict(Parser().parsestr(data.encode('UTF-8', 'replace')).items())

    package_data = {'name': pop_key(attrs, 'Name'),
                    'summary': pop_key(attrs, 'Summary', None),
                    'license': pop_key(attrs, 'License', None)}

    release_data = {'version': pop_key(attrs, 'Version'),
                    'description': pop_key(attrs, 'Description', None),
                    'home_page': pop_key(attrs, 'Home-page', None)}

    file_data = {'basename': path.basename(filename),
                 'attrs': {
                     'packagetype': 'bdist_egg',
                     'python_version': 'source'}
                 }

    return package_data, release_data, file_data


def inspect_pypi_package_exe(filename):
    # ipython-0.12.1.win-amd64.exe
    name_version, windist = filename[:-4].rsplit('.', 1)

    name, version = name_version.split('-', 1)

    package_data = {'name': name}
    release_data = {'version': version}

    file_data = {'attrs': {'packagetype': 'bdist_wininst',
                           'python_version': 'source',
                           'windist': windist},
                 'basename': path.basename(filename)}

    return package_data, release_data, file_data


def inspect_pypi_package_rpm(filename):
    # ipython-0.12.1.win-amd64.exe
    name_version, rpmarch = filename[:-4].rsplit('.', 1)

    name, version, python_version = name_version.split('-', 2)

    package_data = {'name': name}
    release_data = {'version': version}

    file_data = {'attrs': {'packagetype': 'bdist_rpm',
                           'python_version': python_version,
                           'rpmarch': rpmarch},
                 'basename': path.basename(filename)}

    return package_data, release_data, file_data


def inspect_pypi_package(filename, fileobj, *args, **kwargs):
    if filename.endswith('.tar.gz') or filename.endswith('.tar.bz2'):
        return inspect_pypi_package_sdist(filename, fileobj)
    if filename.endswith('.whl'):
        return inspect_pypi_package_whl(filename, fileobj)
    if filename.endswith('.egg'):
        return inspect_pypi_package_egg(filename, fileobj)
    if filename.endswith('.zip'):
        return inspect_pypi_package_zip(filename, fileobj)
    if filename.endswith('.exe'):
        return inspect_pypi_package_exe(filename)
    if filename.endswith('.rpm'):
        return inspect_pypi_package_rpm(filename)

    _, etx = path.splitext(filename)
    raise errors.NoMetadataError(
        'Can not inspect {} package with file with extension {}'.format(PackageType.STANDARD_PYTHON, etx))


# Test Package: https://pypi.python.org/packages/source/F/Flask-Bower/Flask-Bower-1.1.1.tar.gz
# Test Package: https://pypi.python.org/packages/2.7/i/ipython/ipython-3.0.0-py2-none-any.whl
# Test Package: https://pypi.python.org/packages/source/i/ipython/ipython-3.0.0.tar.gz


def main():
    from pprint import pprint

    filename = sys.argv[1]

    if filename.startswith('https://') or filename.startswith('http://'):
        import io
        import requests
        data = requests.get(filename, stream=True, timeout=10 * 60 * 60).raw.read()
        fileobj = io.BytesIO(data)
    else:
        fileobj = open(filename)

    package_data, release_data, file_data = inspect_pypi_package(filename, fileobj)
    pprint(package_data)
    print('--')
    pprint(release_data)
    print('--')
    pprint(file_data)


if __name__ == '__main__':
    main()
