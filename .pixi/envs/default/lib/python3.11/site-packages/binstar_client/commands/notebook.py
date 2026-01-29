# pylint: disable=missing-function-docstring

"""
[Deprecation warning]
`anaconda notebook` is going to be deprecated
use `anaconda upload/download` instead
"""

import argparse
import logging
import sys
from binstar_client.deprecations import DEPRECATION_MESSAGE_NOTEBOOKS_PROJECTS_ENVIRONMENTS_REMOVED

logger = logging.getLogger('binstar.notebook')


def main(args):  # pylint: disable=unused-argument
    logger.error(DEPRECATION_MESSAGE_NOTEBOOKS_PROJECTS_ENVIRONMENTS_REMOVED)
    return sys.exit(1)


def add_parser(subparsers):
    description = 'Interact with notebooks in your Anaconda repository'
    parser = subparsers.add_parser('notebook',
                                   formatter_class=argparse.RawDescriptionHelpFormatter,
                                   help=description,
                                   description=description,
                                   epilog=__doc__)
    parser.add_argument(
        'args',
        nargs='+',
        help='Catch-all for args',
        action='store'
    )

    parser.set_defaults(main=main)
