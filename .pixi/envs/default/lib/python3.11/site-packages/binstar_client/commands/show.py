# pylint: disable=missing-function-docstring

"""
Show information about an object

Examples:

    anaconda show continuumio
    anaconda show continuumio/python
    anaconda show continuumio/python/2.7.5
    anaconda show sean/meta/1.2.0/meta.tar.gz
"""

import logging

from argparse import RawTextHelpFormatter

from binstar_client.utils import get_server_api, parse_specs
from binstar_client.utils.config import PackageType
from binstar_client.utils.pprint import format_package_type, pprint_user, pprint_packages, pprint_orgs

logger = logging.getLogger('binstar.show')


def install_info(package, package_type):
    if package_type is PackageType.STANDARD_PYTHON:
        logger.info('To install this package with %s run:', package_type.value)
        if package['public']:
            url = 'https://pypi.anaconda.org/%s/simple' % package['owner']['login']
        else:
            url = 'https://pypi.anaconda.org/t/$TOKEN/%s/simple' % package['owner']['login']

        logger.info('     pip install -i %s %s', url, package['name'])
    if package_type is PackageType.CONDA:
        logger.info('To install this package with %s run:', package_type.value)
        if package['public']:
            url = 'https://conda.anaconda.org/%s', package['owner']['login']
        else:
            url = 'https://conda.anaconda.org/t/$TOKEN/%s' % package['owner']['login']

        logger.info('     conda install --channel %s %s', url, package['name'])


def main(args):

    aserver_api = get_server_api(args.token, args.site)

    spec = args.spec
    if spec._basename:  # pylint: disable=protected-access
        dist = aserver_api.distribution(spec.user, spec.package, spec.version, spec.basename)
        logger.info(dist.pop('basename'))
        logger.info(dist.pop('description') or 'no description')
        logger.info('')
        metadata = dist.pop('attrs', {})
        for key, value in dist.items():
            logger.info('%-25s: %r', key, value)
        logger.info('Metadata:')
        for key, value in metadata.items():
            logger.info('    + %-25s: %r', key, value)

    elif args.spec._version:  # pylint: disable=protected-access
        logger.info('version %s', spec.version)
        release = aserver_api.release(spec.user, spec.package, spec.version)
        for dist in release['distributions']:
            logger.info('   + %(basename)s', dist)
        logger.info(release.get('public_attrs', {}).get('description'))

    elif args.spec._package:  # pylint: disable=protected-access
        package = aserver_api.package(spec.user, spec.package)
        package['access'] = 'public' if package['public'] else 'private'

        package_types = ', '.join(format_package_type(item) for item in (package.get('package_types', None) or ()))

        logger.info('Name:    %(name)s', package)
        logger.info('Summary: %(summary)s', package)
        logger.info('Access:  %(access)s', package)
        logger.info('Package Types:  %s', package_types)
        logger.info('Versions:')
        for release in package['releases']:
            logger.info('   + %(version)s', release)

        logger.info('')
        for package_type in package.get('package_types'):
            install_info(package, PackageType(package_type))

        if not package['public']:
            logger.info('To generate a $TOKEN run:')
            logger.info('    TOKEN=$(anaconda auth --create --name <TOKEN-NAME>)')

    elif args.spec._user:  # pylint: disable=protected-access
        user_info = aserver_api.user(spec.user)
        pprint_user(user_info)
        pprint_packages(aserver_api.user_packages(spec.user))
        if user_info['user_type'] == 'user':
            pprint_orgs(aserver_api.user_orgs(spec.user))

    else:
        logger.info(args.spec)


def add_parser(subparsers):
    description = 'Show information about an object'
    parser = subparsers.add_parser('show',
                                   help=description, description=description,
                                   epilog=__doc__,
                                   formatter_class=RawTextHelpFormatter)

    parser.add_argument('spec', type=parse_specs,
                        help='Package written as USER[/PACKAGE[/VERSION[/FILE]]]')

    parser.set_defaults(main=main)
