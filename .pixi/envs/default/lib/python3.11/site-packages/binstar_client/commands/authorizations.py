# pylint: disable=missing-function-docstring

"""
Manage Authentication tokens

See also:

* [Using Anaconda.org Tokens](
  https://docs.anaconda.org/free/anacondaorg/user-guide/tasks/work-with-accounts/#cloud-accounts-tokens)

"""

from __future__ import print_function

import argparse
import datetime
import getpass
import logging
import socket
import sys
import typing

import pytz
from dateutil.parser import parse as parse_date

from binstar_client import errors
from binstar_client.utils import get_server_api
from binstar_client.utils import tables

if typing.TYPE_CHECKING:
    import typing_extensions


logger = logging.getLogger('binstar.auth')


SCOPE_EXAMPLES: 'typing_extensions.Final[str]' = """

Examples

To allow access to only conda downloads from your account you can run:

    anaconda auth --create --scopes 'repos conda:download'

To allow full access to your account:

    anaconda auth --create --scopes 'all'

"""


class TimeDeltaGroup(typing.NamedTuple):
    """
    Rule to format timedelta.

    :param amount: maximum allowed amount for this group.

                   if actual value exceeds it - this rule is skipped and next should be processed.

    :param strict: if set to :code:`True` - actual value would be divided by :code:`amount` before checking next rules.

    :param format: format string that should be used to format the output value.

    :param name: name of the units to display.
    """

    amount: int
    strict: bool
    format: str
    name: str


TIME_DELTA_GROUPS: 'typing_extensions.Final[typing.Sequence[TimeDeltaGroup]]' = (
    TimeDeltaGroup(amount=60, strict=True, format='d', name='second'),
    TimeDeltaGroup(amount=60, strict=True, format='d', name='minute'),
    TimeDeltaGroup(amount=24, strict=True, format='1.1f', name='hour'),
    TimeDeltaGroup(amount=3, strict=False, format='1.1f', name='day'),
    TimeDeltaGroup(amount=0, strict=False, format='d', name='day'),
)


def format_timedelta(date: typing.Optional[datetime.datetime], expired: bool = True) -> str:
    if not date:
        return 'never'

    result: str = ''
    now: datetime.datetime = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    if date < now:
        if expired:
            return 'expired'

        now, date = date, now
        result = ' ago'

    group: TimeDeltaGroup
    delta: typing.Union[int, float] = (date - now).total_seconds()
    for group in TIME_DELTA_GROUPS:
        if delta > group.amount > 0:
            if group.strict:
                delta /= group.amount
            continue

        if group.format.endswith('d'):
            delta = int(delta)

        if delta != 1:
            result = f's{result}'

        return f'{delta:{group.format}} {group.name}{result}'

    return 'unknown'


def show_auths(authentications: typing.Sequence[typing.Mapping[str, typing.Any]]) -> None:
    table: tables.SimpleTableWithAliases = tables.SimpleTableWithAliases(
        aliases=(
            ('id', 'ID'),
            ('application', 'Application'),
            ('remote_addr', 'Remote Addr'),
            ('hostname', 'Host'),
            ('expires', 'Expires In'),
            ('scopes', 'Scopes'),
        ),
        heading_rows=1,
    )

    auth: typing.Mapping[str, typing.Any]
    for auth in authentications:
        auth = {
            **auth,
            'expires': format_timedelta(parse_date(auth['expires']) if auth['expires'] else None),
        }

        first: bool = True
        for scope in auth['scopes'] or ('NO_SCOPE',):
            auth['scopes'] = scope
            table.append_row(auth)
            if first:
                first = False
                auth = {}

    logger.info('')
    for line in table.render(tables.SIMPLE):
        logger.info(line)
    logger.info('')


def main(args):  # pylint: disable=too-many-branches
    aserver_api = get_server_api(args.token, args.site)
    if args.info:
        data = aserver_api.authentication()
        logger.info('Name: %s', data['application'])
        logger.info('Id: %s', data['id'])
    if args.list:  # pylint: disable=no-else-return
        show_auths(aserver_api.authentications())
        return
    elif args.remove:
        for auth_name in args.remove:
            aserver_api.remove_authentication(auth_name, args.organization)
            logger.info('Removed token %s', auth_name)
        return
    elif args.list_scopes:
        scopes = aserver_api.list_scopes()
        for key in sorted(scopes):
            logger.info(key)
            logger.info('  %s', scopes[key])
            logger.info('')
        logger.info(SCOPE_EXAMPLES)

    elif args.create:
        auth_type = aserver_api.authentication_type()

        try:
            current_user = aserver_api.user()
            username = current_user['login']
        except Exception:  # pylint: disable=broad-except
            if auth_type == 'kerberos':
                logger.error("Kerberos authentication needed, please use 'anaconda login' to authenticate")
                return

            current_user = None
            sys.stderr.write('Username: ')
            sys.stderr.flush()
            username = input('')

        scopes = [scope for scopes in args.scopes for scope in scopes.split()]
        if not scopes:
            logger.warning('You have not specified the scope of this token with the \'--scopes\' argument.')
            logger.warning('This token will grant full access to %s\'s account', args.organization or username)
            logger.warning('Use the --list-scopes option to see a listing of your options')

        for _ in range(3):
            try:
                if auth_type == 'kerberos':
                    token = aserver_api._authenticate(  # pylint: disable=protected-access
                        None,
                        args.name,
                        application_url=args.url,
                        scopes=scopes,
                        for_user=args.organization,
                        max_age=args.max_age,
                        strength=args.strength,
                        fail_if_already_exists=True
                    )
                else:
                    sys.stderr.write("Please re-enter %s's " % username)
                    password = getpass.getpass()
                    token = aserver_api.authenticate(
                        username, password,
                        args.name,
                        application_url=args.url,
                        scopes=scopes,
                        for_user=args.organization,
                        max_age=args.max_age,
                        strength=args.strength,
                        fail_if_already_exists=True
                    )
                args.out.write(token)
                break
            except errors.Unauthorized:
                logger.error('Invalid Username password combination, please try again')
                continue


def add_parser(subparsers):
    description = 'Manage Authorization Tokens'
    parser = subparsers.add_parser('auth',
                                   help=description,
                                   description=description,
                                   epilog=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '-n', '--name',
        default='binstar_token:%s' % (socket.gethostname()),
        help='A unique name so you can identify this token later. View your tokens at anaconda.org/settings/access'
    )

    parser.add_argument('-o', '--org', '--organization',
                        help='Set the token owner (must be an organization)', dest='organization')

    token_group = parser.add_argument_group('token creation arguments',
                                            'These arguments are only valid with the `--create` action')

    token_group.add_argument('--strength', choices=['strong', 'weak'], default='strong', dest='strength')
    token_group.add_argument('--strong', action='store_const', const='strong',
                             dest='strength', help='Create a longer token (default)')
    token_group.add_argument('-w', '--weak', action='store_const', const='weak',
                             dest='strength', help='Create a shorter token')

    token_group.add_argument('--url', default='http://anaconda.org',
                             help='The url of the application that will use this token')
    token_group.add_argument('--max-age', type=int, help='The maximum age in seconds that this token will be valid for')
    token_group.add_argument(
        '-s', '--scopes', action='append',
        help=('Scopes for token. ' +
              'For example if you want to limit this token to conda downloads only you would use ' +
              '--scopes "repo conda:download"'),
        default=[]
    )

    token_group.add_argument('--out', default=sys.stdout, type=argparse.FileType('w'))

    group = parser.add_argument_group('actions')
    group = group.add_mutually_exclusive_group(required=True)
    group.add_argument('-x', '--list-scopes', action='store_true', help='list all authentication scopes')
    group.add_argument('-l', '--list', action='store_true', help='list all user authentication tokens')
    group.add_argument('-r', '--remove', metavar='NAME', nargs='+', help='remove authentication tokens')
    group.add_argument('-c', '--create', action='store_true', help='Create an authentication token')
    group.add_argument('-i', '--info', '--current-info', dest='info',
                       action='store_true', help='Show information about the current authentication token')

    parser.set_defaults(main=main)
