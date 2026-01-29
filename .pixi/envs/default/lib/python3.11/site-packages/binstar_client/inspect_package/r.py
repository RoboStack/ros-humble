# pylint: disable=missing-module-docstring,missing-function-docstring

import tarfile
import email.parser
from os import path

# Python 3 requires BytesParser which doesn't exist in Python 2
Parser = getattr(email.parser, 'BytesParser', email.parser.Parser)


def parse_package_list(package_spec):
    if not package_spec:
        return []

    return [
        spec.strip()
        for spec in package_spec.split(',')
    ]


def inspect_r_package(filename, fileobj, *args, **kwargs):  # pylint: disable=unused-argument,too-many-locals

    with tarfile.open(filename, fileobj=fileobj) as tar_file:
        pkg_info = next(name for name in tar_file.getnames() if name.endswith('/DESCRIPTION'))
        tar_file_descriptor = tar_file.extractfile(pkg_info)
        raw_attrs = dict(Parser().parse(tar_file_descriptor).items())

    name = raw_attrs.pop('Package')
    version = raw_attrs.pop('Version')
    summary = raw_attrs.pop('Title', None)
    description = raw_attrs.pop('Description', None)
    _license = raw_attrs.pop('License', None)

    attrs = {}
    attrs['NeedsCompilation'] = raw_attrs.get('NeedsCompilation', 'no')
    attrs['depends'] = parse_package_list(raw_attrs.get('Depends'))
    attrs['suggests'] = parse_package_list(raw_attrs.get('Suggests'))

    built = raw_attrs.get('Built')

    if built:
        r, _, date, platform = built.split(';')  # pylint: disable=unused-variable
        r_version = r.strip('R ')
        attrs['R'] = r_version
        attrs['os'] = platform.strip()
        attrs['type'] = 'package'
    else:
        attrs['type'] = 'source'

    package_data = {'name': name,
                    'summary': summary,
                    'license': _license,
                    }
    release_data = {
        'version': version,
        'description': description,
    }
    file_data = {
        'basename': path.basename(filename),
        'attrs': attrs,
    }

    return package_data, release_data, file_data
