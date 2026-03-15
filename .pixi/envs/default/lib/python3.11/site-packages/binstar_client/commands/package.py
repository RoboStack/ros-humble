"""
Anaconda repository package utilities
"""

from __future__ import print_function

import logging
from argparse import Namespace
from typing import Optional

import typer

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
        aserver_api.add_package(
            args.spec.user,
            args.spec.package,
            args.summary,
            public=public,
            license=args.license,
            license_url=args.license_url,
        )
        logger.info('Package created!')


def add_parser(subparsers):
    parser = subparsers.add_parser('package', help='Package utils', description=__doc__)

    parser.add_argument('spec', help='Package to operate on', type=parse_specs, metavar='USER/PACKAGE')
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
    group.add_argument(
        '--personal',
        action='store_const',
        const='personal',
        dest='access',
        help=('Set the package access to personal This package will be available only on your personal registries'),
    )
    group.add_argument(
        '--private',
        action='store_const',
        const='private',
        dest='access',
        help=(
            'Set the package access to private This package will require authorized and authenticated access to install'
        ),
    )

    parser.set_defaults(main=main)


def _exclusive_action(ctx: typer.Context, param: typer.CallbackParam, value: str) -> str:
    """Check for exclusivity of action options.

    To do this, we attach a new special attribute onto the typer Context the first time
    one of the options in the group is used.

    """
    if getattr(ctx, '_actions', None) is None:
        ctx._actions = set()  # type: ignore[attr-defined]
    if value:
        if ctx._actions:  # type: ignore[attr-defined]
            (used_action,) = ctx._actions  # type: ignore[attr-defined]
            raise typer.BadParameter(f'mutually exclusive with {used_action}')
        ctx._actions.add(' / '.join(f"'{o}'" for o in param.opts))  # type: ignore[attr-defined]
    return value


def mount_subcommand(app: typer.Typer, name: str, hidden: bool, help_text: str, context_settings: dict) -> None:
    @app.command(
        name=name,
        hidden=hidden,
        help=help_text,
        context_settings=context_settings,
        no_args_is_help=True,
    )
    def package_subcommand(
        ctx: typer.Context,
        spec: str = typer.Argument(
            ...,
            help='Package to operate on',
            parser=parse_specs,
        ),
        add_collaborator: Optional[str] = typer.Option(
            None,
            help='username of the collaborator you want to add',
            callback=_exclusive_action,
        ),
        list_collaborators: bool = typer.Option(
            False,
            help='list all of the collaborators in a package',
            callback=_exclusive_action,
        ),
        create: bool = typer.Option(
            False,
            help='Create a package',
            callback=_exclusive_action,
        ),
        summary: Optional[str] = typer.Option(
            None,
            help='Set the package short summary',
        ),
        license_: Optional[str] = typer.Option(
            None,
            '--license',
            help='Set the package license',
        ),
        license_url: Optional[str] = typer.Option(
            None,
            help='Set the package license url',
        ),
        personal: bool = typer.Option(
            False,
            help=('Set the package access to personal This package will be available only on your personal registries'),
        ),
        private: bool = typer.Option(
            False,
            help=(
                'Set the package access to private '
                'This package will require authorized and authenticated access to install'
            ),
        ),
    ) -> None:
        if not any([add_collaborator, list_collaborators, create]):
            raise typer.BadParameter('one of --add-collaborator, --list-collaborators, or --create must be provided')

        if private and personal:
            raise typer.BadParameter('Cannot set both --private and --personal')

        if private:
            access = 'private'
        elif personal:
            access = 'personal'
        else:
            access = None

        args = Namespace(
            token=ctx.obj.params.get('token'),
            site=ctx.obj.params.get('site'),
            spec=spec,
            add_collaborator=add_collaborator,
            list_collaborators=list_collaborators,
            create=create,
            summary=summary,
            license=license_,
            license_url=license_url,
            access=access,
        )

        main(args)
