# pylint: disable=missing-function-docstring

"""
Anaconda repository package utilities
"""

from __future__ import print_function

import logging

from binstar_client.utils import get_server_api, parse_specs

logger = logging.getLogger('binstar.package')


def main(args):

    aserver_api = get_server_api(args.token, args.site)
    spec = args.spec

    owner = spec.user
    package = spec.package

    if args.add_collaborator:
        collaborator = args.add_collaborator
        aserver_api.package_add_collaborator(owner, package, collaborator)

    elif args.list_collaborators:
        logger.info(':Collaborators:')
        for collab in aserver_api.package_collaborators(owner, package):
            logger.info(collab['login'])
    elif args.create:
        public = args.access != 'private'
        aserver_api.add_package(args.spec.user, args.spec.package, args.summary,
                                public=public,
                                license=args.license, license_url=args.license_url)
        logger.info('Package created!')


def add_parser(subparsers):

    parser = subparsers.add_parser('package',
                                   help='Package utils',
                                   description=__doc__)

    parser.add_argument('spec', help='Package to operate on', type=parse_specs,
                        metavar='USER/PACKAGE')
    agroup = parser.add_argument_group('actions')
    group = agroup.add_mutually_exclusive_group(required=True)
    group.add_argument('--add-collaborator', metavar='user', help='username of the collaborator you want to add')
    group.add_argument('--list-collaborators', action='store_true', help='list all of the collaborators in a package')
    group.add_argument('--create', action='store_true', help='Create a package')

    mgroup = parser.add_argument_group('metadata arguments')
    mgroup.add_argument('--summary', help='Set the package short summary')
    mgroup.add_argument('--license', help='Set the package license')
    mgroup.add_argument('--license-url', help='Set the package license url')

    pgroup = parser.add_argument_group('privacy')
    group = pgroup.add_mutually_exclusive_group(required=False)
    group.add_argument('--personal', action='store_const', const='personal', dest='access',
                       help=('Set the package access to personal '
                             'This package will be available only on your personal registries'))
    group.add_argument('--private', action='store_const', const='private', dest='access',
                       help=('Set the package access to private '
                             'This package will require authorized and authenticated access to install'))

    parser.set_defaults(main=main)
