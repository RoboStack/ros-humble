# pylint: disable=missing-function-docstring

"""
Log out from binstar
"""

import logging

from binstar_client import errors
from binstar_client.utils import get_server_api, remove_token

logger = logging.getLogger('binstar.logout')


def main(args):
    aserver_api = get_server_api(args.token, args.site)
    if aserver_api.token:
        # NOTE: named 'application' because I was using the github model
        # Change it to name once we release the latest version of binstar server
        try:
            aserver_api.remove_authentication()
        except errors.Unauthorized as err:
            logger.debug('The token that you are trying to remove may not be valid %s', err)

        remove_token(args)
        logger.info('logout successful')
    else:
        logger.info('You are not logged in')


def add_parser(subparsers):
    subparser = subparsers.add_parser('logout',
                                      help='Log out from your Anaconda repository',
                                      description=__doc__)

    subparser.set_defaults(main=main)
