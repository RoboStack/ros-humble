"""Authenticate a user."""

from __future__ import unicode_literals

import getpass
import logging
import os
import platform
import re
import socket
import sys
from urllib.parse import urlparse, urljoin

from anaconda_auth.actions import _do_auth_flow
from anaconda_auth.config import AnacondaAuthSite
from anaconda_auth.token import TokenInfo
from anaconda_auth.exceptions import TokenNotFoundError
from binstar_client import errors
from binstar_client.utils import get_config, get_server_api, store_token, bool_input

LEGACY_INTERACTIVE_LOGIN = os.getenv("ANACONDA_CLIENT_LEGACY_INTERACTIVE_LOGIN", False)

logger = logging.getLogger('binstar.login')


class DotOrgSite(AnacondaAuthSite):
    @property
    def domain_for_keyring_token(self):
        # The unified CLI/SDK does not prefer the "auth." subdomain
        # API Keys generated from `anaconda login` are stored in the
        # keyring without the "auth." subdomain.
        domain = re.sub(r"^auth\.", "", urlparse(self.oidc.authorization_endpoint).netloc)
        return domain

    @property
    def login_success_url(self) -> str:
        """The location to redirect after auth flow, if successful."""
        return urljoin(f"https://{self.domain_for_keyring_token}", self.login_success_path)

    @property
    def login_error_url(self) -> str:
        """The location to redirect after auth flow, if there is an error."""
        return urljoin(f"https://{self.domain_for_keyring_token}", self.login_error_path)


def get_anaconda_unified_token(url):
    """Retrieve an anaconda unified auth credential, either a stored API key or a new
    access token retrieved via interactive login.
    """
    dot_org_api_domain = urlparse(url).netloc
    config = DotOrgSite(domain=dot_org_api_domain)

    try:
        anaconda_token = TokenInfo.load(domain=config.domain_for_keyring_token).api_key
    except TokenNotFoundError:
        anaconda_token = _do_auth_flow(config=config)

    return anaconda_token


def try_replace_token(authenticate, **kwargs):
    """Authenticates using the given *authenticate*, retrying if the token needs to be replaced."""

    try:
        return authenticate(**kwargs)
    except errors.BinstarError as err:
        if kwargs.get('fail_if_already_exists', False) and (len(err.args) >= 2) and (err.args[1] == 400):
            logger.warning('It appears you are already logged in from host %s', socket.gethostname())
            logger.warning(
                'Logging in again will remove the previous token. (This could cause troubles with virtual machines '
                'with the same hostname)'
            )
            logger.warning('Otherwise you can login again and specify a different hostname with "--hostname"')

            if bool_input('Would you like to continue'):
                kwargs['fail_if_already_exists'] = False
                return authenticate(**kwargs)
            else:
                # Exit before we try to overwrite the token
                raise SystemExit(1)

        raise


def interactive_get_token(args, fail_if_already_exists=True):
    api_client = get_server_api(args.token, args.site)
    config = get_config(site=args.site)

    token = None
    # This function could be called from a totally different CLI, so we don't
    # know if the attribute hostname exists.
    hostname = getattr(args, 'hostname', platform.node())
    site = args.site or config.get('default_site')
    url = config.get('url', 'https://api.anaconda.org')

    auth_name = 'binstar_client:'
    if site and site not in ('binstar', 'anaconda'):
        # For testing with binstar alpha site
        auth_name += '%s:' % site

    auth_name += '%s@%s' % (getpass.getuser(), hostname)

    api_client.check_server()

    has_legacy_flags = getattr(args, "login_username", None) or getattr(args, "login_password", None)

    if not (LEGACY_INTERACTIVE_LOGIN or has_legacy_flags):
        # If the user already has a token, prompt them if they want to login again.
        # This is to prevent the browser auth flow required by `get_anaconda_unified_token`.
        if api_client.token is not None:
            logger.warning('It appears you are already logged into %s', api_client.domain)
            logger.warning('Logging in again will remove the previous token.')
            if not bool_input('Would you like to continue'):
                # Exit before we try to overwrite the token
                raise SystemExit(1)

        anaconda_token = get_anaconda_unified_token(url)

        try:
            token = try_replace_token(
                api_client.bearer_authentication,
                auth=anaconda_token,
                application=auth_name,
                application_url=url,
                fail_if_already_exists=False,  # Overwrite because user has already confirmed
                hostname=hostname,
            )
        except errors.Unauthorized as e:
            # This is the error state before the unified auth support is deployed on anaconda.org
            if e.message == "Bearer token authentication is not enabled":
                logger.warning("Server does not support unified auth yet, defaulting to legacy login flow")
            else:
                # If we don't have a specific error, we just raise it
                raise
        else:
            return token

    logger.warning('Username/password login is deprecated')
    auth_type = api_client.authentication_type()

    if auth_type == 'kerberos':
        token = try_replace_token(
            api_client.krb_authenticate,
            application=auth_name,
            application_url=url,
            fail_if_already_exists=fail_if_already_exists,
            hostname=hostname,
        )

        if token is None:
            raise errors.BinstarError(
                'Unable to authenticate via Kerberos. Try refreshing your authentication using `kinit`'
            )
    else:
        if getattr(args, 'login_username', None):
            username = args.login_username
        else:
            username = input('Username: ')

        password = getattr(args, 'login_password', None)

        for _ in range(3):
            try:
                sys.stderr.write("%s's " % username)

                if password is None:
                    password = getpass.getpass(stream=sys.stderr)

                token = try_replace_token(
                    api_client.authenticate,
                    username=username,
                    password=password,
                    application=auth_name,
                    application_url=url,
                    fail_if_already_exists=fail_if_already_exists,
                    hostname=hostname,
                )
                break

            except errors.Unauthorized:
                logger.error('Invalid Username password combination, please try again')
                password = None
                continue

        if token is None:
            parsed_url = urlparse(url)
            if parsed_url.netloc.startswith('api.anaconda.org'):
                netloc = 'anaconda.org'
            else:
                netloc = parsed_url.netloc
            hostparts = (parsed_url.scheme, netloc)
            msg = (
                'Sorry. Please try again '
                + '(go to %s://%s/account/forgot_password ' % hostparts
                + 'to reset your password)'
            )
            raise errors.BinstarError(msg)

    return token


def interactive_login(args):
    token = interactive_get_token(args)
    store_token(token, args)
    logger.info('login successful')


def main(args):
    interactive_login(args)


def add_parser(subparsers):
    subparser = subparsers.add_parser('login', help='Authenticate a user', description=__doc__)
    subparser.add_argument(
        '--hostname',
        default=platform.node(),
        help='Specify the host name of this login, this should be unique (default: %(default)s)',
    )
    subparser.add_argument(
        '--username',
        dest='login_username',
        help='(deprecated) Specify your username. If this is not given, you will be prompted',
    )
    subparser.add_argument(
        '--password',
        dest='login_password',
        help='(deprecated) Specify your password. If this is not given, you will be prompted',
    )
    subparser.set_defaults(main=main)
