"""
Search your Anaconda repository for packages.
"""

import argparse
import logging
from enum import Enum
from typing import Optional

import typer

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
        epilog=__doc__,
    )
    parser.add_argument(
        'name',
        nargs=1,
        help='Search string',
    )
    parser.add_argument(
        '-t',
        '--package-type',
        # choices=['conda', 'pypi', 'r'],
        help='only search for packages of this type',
    )
    parser.add_argument(
        '-p',
        '--platform',
        choices=[
            'osx-32',
            'osx-64',
            'win-32',
            'win-64',
            'linux-32',
            'linux-64',
            'linux-aarch64',
            'linux-armv6l',
            'linux-armv7l',
            'linux-ppc64le',
            'linux-s390x',
            'noarch',
        ],
        help='only search for packages of the chosen platform',
    )
    parser.set_defaults(main=search)


class Platform(Enum):
    """An enum representing platforms that can be passed as options."""

    OSX_32 = 'osx-32'
    OSX_64 = 'osx-64'
    WIN_32 = 'win-32'
    WIN_64 = 'win-64'
    LINUX_32 = 'linux-32'
    LINUX_64 = 'linux-64'
    LINUX_AARCH64 = 'linux-aarch64'
    LINUX_ARMV6L = 'linux-armv6l'
    LINUX_ARMV7L = 'linux-armv7l'
    LINUX_PPC64LE = 'linux-ppc64le'
    LINUX_S390X = 'linux-s390x'
    NOARCH = 'noarch'


def mount_subcommand(app: typer.Typer, name: str, hidden: bool, help_text: str, context_settings: dict) -> None:
    @app.command(
        name=name,
        hidden=hidden,
        help=help_text,
        context_settings=context_settings,
        no_args_is_help=True,
    )
    def search_subcommand(
        ctx: typer.Context,
        name: str = typer.Argument(
            help='Search string',
            show_default=False,
        ),
        package_type: Optional[str] = typer.Option(
            None,
            '-t',
            '--package-type',
            help='Only search for packages of this type',
        ),
        platform: Optional[Platform] = typer.Option(
            None,
            '-p',
            '--platform',
            help='Only search for packages of the chosen platform',
        ),
    ) -> None:
        args = argparse.Namespace(
            token=ctx.obj.params.get('token'),
            site=ctx.obj.params.get('site'),
            name=[name],
            package_type=package_type,
            platform=platform.value if platform is not None else None,
        )

        search(args)
