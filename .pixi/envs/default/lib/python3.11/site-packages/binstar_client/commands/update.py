# -*- coding: utf-8 -*-

"""Update public attributes of the package or the attributes of the package release."""

from __future__ import annotations

__all__ = ['add_parser']

import argparse
import json
import logging
import os
import typing

import yaml

from binstar_client import errors
from binstar_client.utils import get_server_api
from binstar_client.utils import parse_specs
from binstar_client.utils import detect

logger = logging.getLogger('binstar.update')


Attributes = typing.Mapping[str, typing.Any]


def get_attributes(package: str, args: argparse.Namespace) -> typing.Tuple[Attributes, Attributes]:
    """Parse source for attribute details."""
    loader: typing.Optional[typing.Callable[[typing.TextIO], detect.PackageAttributes]] = None
    if package.endswith('.json'):
        loader = json.load
    elif package.endswith(('.yml', '.yaml')):
        loader = yaml.safe_load
    if loader is not None:
        stream: typing.TextIO
        with open(package, 'rt', encoding='utf-8') as stream:
            return (loader(stream),) * 2

    package_type: typing.Optional[detect.PackageType]
    if args.package_type:
        package_type = detect.PackageType(args.package_type)
    else:
        package_type = detect.detect_package_type(package)
    if package_type is None:
        message: str = (
            f'Could not detect package type of file "{package}". '
            'Please specify package type with option --package-type'
        )
        logger.error(message)
        raise errors.BinstarError(message)

    try:
        return detect.get_attrs(package_type, package, parser_args=args)[:2]
    except Exception as error:
        message = f'Trouble reading metadata from {package}. Is this a valid source file: {package_type.label}?'
        logger.error(message)
        raise errors.BinstarError(message) from error


def main(args: argparse.Namespace) -> None:
    """Process update request."""
    anaconda_api = get_server_api(args.token, args.site)
    anaconda_api.check_server()

    attrs: Attributes = get_attributes(args.source, args)[bool(args.release)]
    attrs = attrs.get('public_attrs', attrs)

    if args.release:
        anaconda_api.update_release(
            args.spec.user,
            args.spec.package,
            args.spec.version,
            attrs,
        )
    else:
        anaconda_api.update_package(
            args.spec.user,
            args.spec.package,
            attrs,
        )
    logger.info('Package `%s` has been updated!', args.spec)


def file_type(path: str) -> str:
    """Validate argument value, that should be a valid path to file."""
    if os.path.isfile(path):
        return path

    raise argparse.ArgumentTypeError(f'{path} is not a valid path')


def add_parser(subparsers: typing.Any) -> None:
    """Add parser to CLI."""
    parser = subparsers.add_parser(
        'update',
        usage=(
            '\n\tanaconda update [--release] user/package[/version] CONDA_PACKAGE_1.tar.bz2'
            '\n\tanaconda update [--release] user/package[/version] metadata.json'
        ),
        description=__doc__,
    )

    parser.add_argument(
        'spec',
        help='Package name written as `user/package[/version]`',
        type=parse_specs,
    )
    parser.add_argument(
        'source',
        help=(
            'Path to the file that consists of metadata that will be updated in the destination package. '
            'It may be a valid package file or `.json` file with described attributes to update'
        ),
        type=file_type,
    )
    parser.add_argument(
        '-t', '--package-type',
        help='Set the package type. Defaults to autodetect',
    )

    release_group = parser.add_argument_group(title='Update release')
    release_group.add_argument(
        '--release',
        help='Use `source` file to update public attributes of the release specified in `spec`',
        action='store_true'
    )

    parser.set_defaults(main=main)
