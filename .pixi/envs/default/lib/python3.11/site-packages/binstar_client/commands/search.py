# pylint: disable=missing-function-docstring

"""
Search your Anaconda repository for packages.
"""

import logging

from binstar_client.utils import config
from binstar_client.utils import get_server_api
from binstar_client.utils.pprint import pprint_packages

logger = logging.getLogger('binstar.search')


def search(args):
    aserver_api = get_server_api(args.token, args.site)

    package_type = None
    if args.package_type:
        package_type = config.PackageType(args.package_type)

    packages = aserver_api.search(args.name, package_type=package_type, platform=args.platform)
    pprint_packages(packages, access=False)
    logger.info('Found %d packages', len(packages))
    logger.info('\nRun \'anaconda show <USER/PACKAGE>\' to get installation details')


def add_parser(subparsers):
    parser = subparsers.add_parser(
        'search',
        help='Search in your Anaconda repository',
        description='Search in your Anaconda repository',
        epilog=__doc__
    )
    parser.add_argument(
        'name',
        nargs=1,
        help='Search string',
    )
    parser.add_argument(
        '-t', '--package-type',
        # choices=['conda', 'pypi', 'r'],
        help='only search for packages of this type'
    )
    parser.add_argument(
        '-p', '--platform',
        choices=[
            'osx-32', 'osx-64', 'win-32', 'win-64', 'linux-32', 'linux-64', 'linux-aarch64', 'linux-armv6l',
            'linux-armv7l', 'linux-ppc64le', 'linux-s390x', 'noarch',
        ],
        help='only search for packages of the chosen platform'
    )
    parser.set_defaults(main=search)
