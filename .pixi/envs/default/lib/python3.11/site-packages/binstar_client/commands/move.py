# -*- coding: utf-8 -*-

# pylint: disable=broad-except,protected-access,missing-function-docstring

"""
Move packages between labels.
"""

# Standard library imports
from __future__ import unicode_literals, print_function
import logging

# Local imports
from binstar_client import errors
from binstar_client.utils import get_server_api, parse_specs


logger = logging.getLogger('binstar.move')


def main(args):
    aserver_api = get_server_api(args.token, args.site)

    spec = args.spec

    channels = aserver_api.list_channels(spec.user)
    label_text = 'label' if (args.from_label and args.to_label) else 'channel'

    from_label = args.from_label.lower()
    to_label = args.to_label.lower()

    if from_label not in channels:
        raise errors.UserError(
            '{} {} does not exist\n\tplease choose from: {}'.format(
                label_text.title(),
                from_label,
                ', '.join(channels)
            ))

    if from_label == to_label:
        raise errors.UserError('--from-label and --to-label must be different')

    # Add files to to_label
    try:
        aserver_api.add_channel(
            to_label,
            spec.user,
            package=spec.package,
            version=spec._version,
            filename=spec._basename,
        )
    except Exception as error:
        logger.exception(error)

    # Remove files from from_label
    try:
        aserver_api.remove_channel(
            from_label,
            spec.user,
            package=spec.package,
            version=spec._version,
            filename=spec._basename,
        )
    except Exception as error:
        logger.exception(error)

    # for binstar_file in files:
    #     print("Copied file: %(basename)s" % binstar_file)

    # if files:
    #     logger.info("Copied %i files" % len(files))
    # else:
    #     logger.warning("Did not copy any files. Please check your inputs "
    #                    "with \n\n\tanaconda show %s" % spec)


def add_parser(subparsers):
    parser = subparsers.add_parser(
        'move',
        help='Move packages between labels',
        description=__doc__,
    )
    parser.add_argument(
        'spec',
        help='Package - written as user/package/version[/filename] '
             'If filename is not given, move all files in the version',
        type=parse_specs,
    )
    # NOTE: To be implemented later on
    # parser.add_argument(
    #     '--to-owner',
    #     help='User account to move package to (default: your account)',
    # )

    _from = parser.add_mutually_exclusive_group()
    _to = parser.add_mutually_exclusive_group()
    _from.add_argument(
        '--from-label',
        help='Label to move packages from',
        default='main',
    )
    _to.add_argument(
        '--to-label',
        help='Label to move packages to',
        default='main',
    )

    parser.set_defaults(main=main)
