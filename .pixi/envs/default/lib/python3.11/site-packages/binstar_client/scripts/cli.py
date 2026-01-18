# -*- coding: utf8 -*-

"""Anaconda repository command line manager."""

from __future__ import annotations

__all__ = ('main',)

import argparse
from importlib import metadata
import json
import logging
import os
import pkgutil
import sys
import types
import typing

from binstar_client import __version__
from binstar_client import commands
from binstar_client import errors
from binstar_client.commands.login import interactive_login
from binstar_client.utils import logging_utils


logger = logging.getLogger('binstar')


def _get_entry_points(group: str) -> typing.List[metadata.EntryPoint]:
    # The API was changed in Python 3.10, see https://docs.python.org/3/library/importlib.metadata.html#entry-points
    if sys.version_info.major == 3 and sys.version_info.minor < 10:
        return metadata.entry_points().get(group, [])
    return metadata.entry_points().select(group=group)  # type: ignore


def file_or_token(value: str) -> str:
    """
    Retrieve a token from input.

    If :code:`value` is a path to a valid file - content of this file will be returned. Otherwise - value itself is
    returned.
    """
    if os.path.isfile(value):
        stream: typing.TextIO
        with open(value, 'rt', encoding='utf8') as stream:
            result: str = stream.read(8193)
            if len(result) > 8192:
                raise ValueError('file is too large for a token')
            return result.strip()

    if not set('/\\.').isdisjoint(value):
        # This chars will never be in a token value, but may be in a path
        # The error message will be handled by the parser
        raise ValueError()

    return value


def _json_action(action):
    # pylint: disable=protected-access  # intentional access of argparse object members
    a_data = dict(action._get_kwargs())

    if a_data.get('help'):
        a_data['help'] = a_data['help'] % a_data

    if isinstance(action, argparse._SubParsersAction):
        a_data.pop('choices', None)
        choices = {}
        for choice in action._get_subactions():
            choices[choice.dest] = choice.help
        a_data['choices'] = choices

    reg = {value: key for key, value in action.container._registries['action'].items()}
    a_data['action'] = reg.get(type(action), type(action).__name__)
    if a_data['action'] == 'store' and not a_data.get('metavar'):
        a_data['metavar'] = action.dest.upper()

    a_data.pop('type', None)
    a_data.pop('default', None)

    return a_data


def _json_group(group):
    # pylint: disable=protected-access  # intentional access of argparse object members
    grp_data = {
        'description': group.description,
        'title': group.title,
        'actions': [_json_action(action) for action in group._group_actions if action.help != argparse.SUPPRESS],
    }

    if group._action_groups:
        grp_data['groups'] = [_json_group(group) for group in group._action_groups]

    return grp_data


class _JSONHelp(argparse.Action):
    # pylint: disable-next=redefined-builtin
    def __init__(self, option_strings, dest, nargs=0, help=argparse.SUPPRESS, **kwargs):
        argparse.Action.__init__(self, option_strings, dest, nargs=nargs, help=help, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # pylint: disable=protected-access  # intentional access of argparse object members
        self.nargs = 0
        docs = {
            'prog': parser.prog,
            'usage': parser.format_usage()[7:],
            'description': parser.description,
            'epilog': parser.epilog,
        }

        docs['groups'] = []
        for group in parser._action_groups:
            if group._group_actions:
                docs['groups'].append(_json_group(group))

        json.dump(docs, sys.stdout, indent=2)
        raise SystemExit(0)


def _get_sub_command_names(module):
    return [name for _, name, _ in pkgutil.iter_modules([os.path.dirname(module.__file__)]) if not name.startswith('_')]


def _get_sub_commands(module):
    names = _get_sub_command_names(module)
    this_module = __import__(module.__package__ or module.__name__, fromlist=names)

    for name in names:
        yield getattr(this_module, name)


def _add_subparser_modules(parser, module=None, entry_point_name=None):

    subparsers = parser.add_subparsers(title='Commands', metavar='')

    if module:  # LOAD sub parsers from module
        for command_module in _get_sub_commands(module):
            command_module.add_parser(subparsers)

    if entry_point_name:  # LOAD sub parsers from setup.py entry_point
        for entry_point in _get_entry_points(entry_point_name):
            add_parser = entry_point.load()
            add_parser(subparsers)

    for key, sub_parser in subparsers.choices.items():
        sub_parser.set_defaults(sub_command_name=key)
        sub_parser.add_argument('--json-help', action=_JSONHelp)


def binstar_main(
        sub_command_module: types.ModuleType,
        args: typing.Optional[typing.Sequence[str]] = None,
        exit_: bool = True,
) -> int:
    """Run `anaconda-client` cli utility."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_argument_group('output')
    group.add_argument(
        '--disable-ssl-warnings', action='store_true', default=False,
        help='Disable SSL warnings (default: %(default)s)',
    )
    group.add_argument(
        '--show-traceback', action='store_true',
        help='Show the full traceback for chalmers user errors (default: %(default)s)',
    )
    group.add_argument(
        '-v', '--verbose', action='store_const', dest='log_level', default=logging.INFO, const=logging.DEBUG,
        help='print debug information on the console',
    )
    group.add_argument(
        '-q', '--quiet', action='store_const', dest='log_level', const=logging.WARNING,
        help='Only show warnings or errors on the console',
    )

    group = parser.add_argument_group('anaconda-client options')
    group.add_argument(
        '-t', '--token', type=file_or_token,
        help='Authentication token to use. May be a token or a path to a file containing a token',
    )
    group.add_argument('-s', '--site', default=None, help='select the anaconda-client site to use')

    if __version__:
        parser.add_argument(
            '-V', '--version', action='version', version=f'%(prog)s Command line client (version {__version__})',
        )

    _add_subparser_modules(parser, sub_command_module, 'conda_server.subcommand')

    arguments: argparse.Namespace = parser.parse_args(args)

    logging_utils.setup_logging(
        logger,
        log_level=arguments.log_level,
        show_traceback=arguments.show_traceback,
        disable_ssl_warnings=arguments.disable_ssl_warnings,
    )

    try:
        try:
            if hasattr(arguments, 'main'):
                return arguments.main(arguments)
            parser.error('A sub command must be given. To show all available sub commands, run:\n\n\t anaconda -h\n')
        except errors.Unauthorized:
            if arguments.token or (not sys.stdin.isatty()):
                raise  # Don't try the interactive login, just exit
            logger.info('The action you are performing requires authentication, please sign in:')
            interactive_login(arguments)
            return arguments.main(arguments)
    except errors.ShowHelp as error:
        arguments.sub_parser.print_help()
        if exit_:
            raise SystemExit(1) from error
        return 1
    return 0  # type: ignore


def _load_main_plugin() -> typing.Optional[typing.Callable[[], typing.Any]]:
    """Allow loading a new CLI main entrypoint via plugin mechanisms. There can only be one."""
    plugin_group_name: typing.Final[str] = 'anaconda_cli.main'

    plugin_mains: typing.List[metadata.EntryPoint] = _get_entry_points(plugin_group_name)

    if len(plugin_mains) > 1:
        raise EnvironmentError(
            'More than one `anaconda_cli.main` plugin is installed. Please ensure only one '
            'of the following packages are installed:\n\n' +
            '\n'.join(f'  * {ep.value}' for ep in plugin_mains)
        )

    if plugin_mains:
        # The `.load()` function returns a callable, which is defined inside the package implementing the plugin
        # e.g. in pyproject.toml, where my_plugin_library.cli.main is the callable entrypoint function
        # [project.entry-points."anaconda_cli.main"]
        # anaconda = "my_plugin_library.cli:main"
        return tuple(plugin_mains)[0].load()
    return None


def main(
        args: typing.Optional[typing.Sequence[str]] = None,
        *,
        exit_: bool = True,
        allow_plugin_main: bool = True,
) -> None:
    """Entrypoint for CLI interface of `anaconda`."""
    if allow_plugin_main and (not os.environ.get('ANACONDA_CLIENT_FORCE_STANDALONE', '')):
        plugged_in_main: typing.Optional[typing.Callable[[], typing.Any]] = _load_main_plugin()
        if plugged_in_main is not None:
            plugged_in_main()
            return

    binstar_main(commands, args, exit_)


if __name__ == '__main__':
    main()
