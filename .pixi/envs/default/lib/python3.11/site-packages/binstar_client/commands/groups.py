# pylint: disable=missing-module-docstring,missing-function-docstring

import logging

from pprint import pformat

from binstar_client.pprintb import package_list, user_list
from binstar_client.utils import get_server_api
from binstar_client.utils.spec import group_spec

logger = logging.getLogger('binstar.groups')


def main(args):
    aserver_api = get_server_api(args.token, args.site)
    spec = args.spec
    action = args.action
    verbose = args.log_level == logging.DEBUG

    if action == 'add':
        aserver_api.add_group(spec.org, spec.group_name, args.perms)
        logger.info('Created the group %s', spec)
    elif action == 'show':
        if spec._group_name:  # pylint: disable=protected-access
            result = aserver_api.group(spec.org, spec.group_name)
        else:
            result = aserver_api.groups(spec.org)
        logger.info(pformat(result))
    elif action == 'members':
        result = aserver_api.group_members(spec.org, spec.group_name)
        logger.info(user_list(result, verbose))
    elif action == 'add_member':
        aserver_api.add_group_member(spec.org, spec.group_name, spec.member)
        logger.info('Added the user "%s" to the group "%s/%s"', spec.member, spec.org,
                    spec.group_name)
    elif action == 'remove_member':
        aserver_api.remove_group_member(spec.org, spec.group_name, spec.member)
        logger.info('Removed the user "%s" from the group "%s/%s"', spec.member, spec.org,
                    spec.group_name)
    elif action == 'packages':
        result = aserver_api.group_packages(spec.org, spec.group_name)
        logger.info(package_list(result, verbose))
    elif action == 'add_package':
        aserver_api.add_group_package(spec.org, spec.group_name, spec.member)
        logger.info('Added the package "%s" to the group "%s/%s"', spec.member, spec.org,
                    spec.group_name)
    elif action == 'remove_package':
        aserver_api.remove_group_package(spec.org, spec.group_name, spec.member)
        logger.info('Removed the package "%s" to the group "%s/%s"', spec.member, spec.org,
                    spec.group_name)
    else:
        raise NotImplementedError(args.action)


def add_parser(subparsers):
    parser = subparsers.add_parser('groups', help='Manage Groups', description=__doc__)

    parser.add_argument('action',
                        choices=['add', 'show', 'members', 'add_member',
                                 'remove_member', 'packages', 'add_package',
                                 'remove_package'],
                        help='The group management command to execute')
    parser.add_argument('spec', type=group_spec,
                        help=group_spec.__doc__)
    parser.add_argument('--perms', choices=['read', 'write', 'admin'], default='read',
                        help='The permission the group should provide')

    parser.set_defaults(main=main)
