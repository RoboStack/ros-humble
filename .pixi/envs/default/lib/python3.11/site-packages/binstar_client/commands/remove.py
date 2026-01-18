# pylint: disable=missing-function-docstring

"""
Remove an object from your Anaconda repository.

example::

    anaconda remove sean/meta/1.2.0/meta.tar.gz

"""

import logging
from argparse import RawTextHelpFormatter

from binstar_client import errors
from binstar_client.utils import get_server_api, parse_specs, \
    bool_input

logger = logging.getLogger('binstar.remove')


def main(args):  # pylint: disable=too-many-branches

    aserver_api = get_server_api(args.token, args.site)

    for spec in args.specs:
        try:
            if spec._basename:  # pylint: disable=protected-access
                msg = 'Are you sure you want to remove file %s ?' % (spec,)
                if args.force or bool_input(msg, False):
                    aserver_api.remove_dist(spec.user, spec.package, spec.version, spec.basename)
                else:
                    logger.warning('Not removing file %s', spec)
            elif spec._version:  # pylint: disable=protected-access
                msg = 'Are you sure you want to remove the package release %s ? (and all files under it?)' % (spec,)
                if args.force or bool_input(msg, False):
                    aserver_api.remove_release(spec.user, spec.package, spec.version)
                else:
                    logger.warning('Not removing release %s', spec)
            elif spec._package:  # pylint: disable=protected-access
                msg = 'Are you sure you want to remove the package %s ? (and all data with it?)' % (spec,)
                if args.force or bool_input(msg, False):
                    aserver_api.remove_package(spec.user, spec.package)
                else:
                    logger.warning('Not removing release %s', spec)
            else:
                logger.error('Invalid package specification: %s', spec)

        except errors.NotFound:
            if args.force:
                logger.warning('', exc_info=True)
                continue
            raise


def add_parser(subparsers):
    parser = subparsers.add_parser(
        'remove',
        help=(
            'Remove an object from your Anaconda repository. '
            'Must refer to the formal package name as it appears in the URL of the package. '
            'Also use anaconda show <USERNAME> to see list of package names. '
            'Example: anaconda remove continuumio/empty-example-notebook'
        ),
        description=__doc__,
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        'specs',
        help='Package written as <user>[/<package>[/<version>[/<filename>]]]',
        type=parse_specs,
        nargs='+',
    )
    parser.add_argument(
        '-f', '--force',
        help='Do not prompt removal',
        action='store_true',
    )

    parser.set_defaults(main=main)
