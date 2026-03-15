import json
import os
import sys
import warnings
from textwrap import dedent
from typing import Annotated
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import typer
from requests.exceptions import HTTPError
from requests.exceptions import JSONDecodeError
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

from anaconda_auth import __version__
from anaconda_auth.actions import login
from anaconda_auth.actions import logout
from anaconda_auth.client import BaseClient
from anaconda_auth.config import AnacondaAuthSite
from anaconda_auth.config import AnacondaAuthSitesConfig
from anaconda_auth.exceptions import TokenExpiredError
from anaconda_auth.exceptions import UnknownSiteName
from anaconda_auth.token import TokenInfo
from anaconda_auth.token import TokenNotFoundError
from anaconda_cli_base.config import anaconda_config_path
from anaconda_cli_base.console import console
from anaconda_cli_base.exceptions import register_error_handler

CHECK_MARK = "[bold green]✔︎[/bold green]"

PROGRAM_ERROR: int = 1
ARGUMENT_ERROR: int = 2
SUCCESS: int = 0


def _continue_with_login() -> int:
    if sys.stdout.isatty():
        do_login = Confirm.ask("Continue with interactive login?", choices=["y", "n"])
        if do_login:
            login()
            return -1
        else:
            console.print(
                dedent("""
                To configure your credentials you can run
                  [green]anaconda login --at anaconda.com[/green]

                or set your API key using the [green]ANACONDA_AUTH_API_KEY[/green] env var

                or set
                """)
            )
            console.print(
                Syntax(
                    dedent(
                        """\
                        [plugin.auth]
                        api_key = "<api-key>"
                        """
                    ),
                    "toml",
                    background_color=None,
                )
            )
            console.print(f"in {anaconda_config_path()}")
    return 1


def _login_required_message(error_classifier: str) -> None:
    console.print(
        f"[bold][red]{error_classifier}[/red][/bold]: Login is required to complete this action."
    )


@register_error_handler(TokenNotFoundError)
def login_required(e: Exception) -> int:
    _login_required_message(e.__class__.__name__)
    return _continue_with_login()


@register_error_handler(TokenExpiredError)
def token_expired(e: Exception) -> int:
    console.print(
        f"[bold][red]{e.__class__.__name__}[/red][/bold]: Your login token has expired"
    )

    return _continue_with_login()


@register_error_handler(HTTPError)
def http_error(e: HTTPError) -> int:
    try:
        error_code = e.response.json().get("error", {}).get("code", "")
    except JSONDecodeError:
        error_code = ""

    if error_code == "auth_required":
        if "Authorization" in e.request.headers:
            console.print(
                "[bold][red]InvalidAuthentication:[/red][/bold] Your provided API Key or login token is invalid"
            )
        else:
            _login_required_message("AuthenticationMissingError")
        return _continue_with_login()
    else:
        console.print(f"[bold][red]{e.__class__.__name__}:[/red][/bold] {e}")
        return 1


def _override_default_site(at: Optional[str] = None) -> None:
    if at:
        os.environ["ANACONDA_DEFAULT_SITE"] = at


app = typer.Typer(
    name="auth",
    add_completion=False,
    help="Manage your Anaconda authentication",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": ["--help", "-h"],
    },
)


@app.callback(
    invoke_without_command=True,
    no_args_is_help=False,
)
def main(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("-V", "--version")] = False,
    name: Annotated[
        Optional[str],
        typer.Option(
            "-n",
            "--name",
            hidden=True,
        ),
    ] = None,
    organization: Annotated[
        Optional[str],
        typer.Option(
            "-o",
            "--org",
            "--organization",
            hidden=True,
        ),
    ] = None,
    strength: Annotated[
        Optional[str],
        typer.Option(
            "--strength",
            hidden=True,
        ),
    ] = None,
    strong: Annotated[
        Optional[bool],
        typer.Option(
            "--strong",
            hidden=True,
        ),
    ] = None,
    weak: Annotated[
        Optional[bool],
        typer.Option(
            "-w",
            "--weak",
            hidden=True,
        ),
    ] = None,
    url: Annotated[
        Optional[str],
        typer.Option(
            "--url",
            hidden=True,
        ),
    ] = None,
    max_age: Annotated[
        Optional[str],
        typer.Option(
            "--max-age",
            hidden=True,
        ),
    ] = None,
    scopes: Annotated[
        Optional[str],
        typer.Option(
            "-s",
            "--scopes",
            hidden=True,
        ),
    ] = None,
    out: Annotated[
        Optional[str],
        typer.Option(
            "--out",
            hidden=True,
        ),
    ] = None,
    list_scopes: Annotated[
        Optional[bool],
        typer.Option(
            "-x",
            "--list-scopes",
            hidden=True,
        ),
    ] = None,
    list_tokens: Annotated[
        Optional[bool],
        typer.Option(
            "-l",
            "--list",
            hidden=True,
        ),
    ] = None,
    remove: Annotated[
        Optional[str],
        typer.Option(
            "-r",
            "--remove",
            hidden=True,
        ),
    ] = None,
    create: Annotated[
        Optional[bool],
        typer.Option(
            "-c",
            "--create",
            hidden=True,
        ),
    ] = None,
    info: Annotated[
        Optional[bool],
        typer.Option(
            "-i",
            "--info",
            "--current-info",
            hidden=True,
        ),
    ] = None,
    extra_args: Annotated[
        Optional[List[str]], typer.Argument(hidden=True, metavar="")
    ] = None,
) -> None:
    if version:
        console.print(
            f"anaconda-auth, version [cyan]{__version__}[/cyan]",
            style="bold green",
        )
        raise typer.Exit(code=SUCCESS)

    # We have to manually handle subcommands due the the handling of the auth subcommand
    # as a top-level subcommand in anaconda-client
    extra_args = extra_args or []
    if extra_args:
        subcommand_name = extra_args[0]
    else:
        subcommand_name = None

    # Extract the subcommands attached to the app. Use dynamic loading just to be safe,
    # because static typing shows this to be invalid.
    subcommands_dict = getattr(ctx.command, "commands", {})

    # If the subcommand is known, then we delegate to the actual functions defined in this module
    if cmd := subcommands_dict.get(subcommand_name):
        cmd.main(
            extra_args[1:], prog_name=subcommand_name, standalone_mode=False, parent=ctx
        )
        return

    has_legacy_options = any(
        value is not None
        for value in (
            name,
            organization,
            strength,
            strong,
            weak,
            url,
            max_age,
            scopes,
            out,
            list_scopes,
            list_tokens,
            remove,
            create,
            info,
        )
    )

    if has_legacy_options or subcommand_name:
        # If any of the anaconda-client options are passed, try to delegate to
        # binstar_main if it exists. Otherwise, we just exit gracefully.

        try:
            from binstar_client.scripts.cli import main as binstar_main
        except (ImportError, ModuleNotFoundError):
            return

        console.print(
            "[yellow]DeprecationWarning[/yellow]: Please use [cyan]anaconda org auth[/cyan] instead for explicit management of anaconda.org auth tokens\n"
        )
        warnings.warn(
            "Please use `anaconda org auth` instead for explicit management of anaconda.org auth tokens",
            DeprecationWarning,
        )

        binstar_main(sys.argv[1:], allow_plugin_main=False)
        return

    # No subcommand was given, so we print help
    console.print(ctx.get_help())


@app.command("login")
def auth_login(
    force: Annotated[bool, typer.Option()] = False,
    ssl_verify: Annotated[
        Optional[bool], typer.Option("--ssl-verify/--no-ssl-verify")
    ] = None,
    at: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Login"""
    _override_default_site(at)
    try:
        token_info = TokenInfo.load()
        domain = token_info.domain
        if token_info.expired:
            console.print(f"Your API key has expired, logging into {domain}")
            login(force=True, ssl_verify=ssl_verify)
            raise typer.Exit(code=SUCCESS)
    except TokenNotFoundError:
        pass  # Proceed to login
    else:
        force = force or Confirm.ask(
            f"You are already logged into Anaconda ({domain}). Would you like to force a new login?",
            default=False,
        )
        if not force:
            raise typer.Exit(code=SUCCESS)

    login(force=force, ssl_verify=ssl_verify)


@app.command(name="whoami")
def auth_info(at: Annotated[Optional[str], typer.Option()] = None) -> None:
    """Display information about the currently signed-in user"""
    _override_default_site(at)
    client = BaseClient()
    response = client.get("/api/account")
    response.raise_for_status()
    console.print(f"Your info ({client.config.domain}):")
    console.print_json(data=response.json(), indent=2, sort_keys=True)


@app.command(name="api-key")
def auth_key(at: Annotated[Optional[str], typer.Option()] = None) -> None:
    """Display API Key for signed-in user"""
    _override_default_site(at)
    token_info = TokenInfo.load()
    if not token_info.expired:
        print(token_info.api_key)
        return
    else:
        raise TokenExpiredError()


@app.command(name="logout")
def auth_logout(at: Annotated[Optional[str], typer.Option()] = None) -> None:
    """Logout"""
    _override_default_site(at)
    logout()


sites_app = typer.Typer(
    name="sites",
    add_completion=False,
    help="Manage your Anaconda site configuration",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": ["--help", "-h"],
    },
)


@sites_app.command(name="list")
def sites_list() -> None:
    """List configured sites by name and domain."""
    sites_config = AnacondaAuthSitesConfig()

    table = Table("Site name", "Domain name", "Default site", header_style="bold green")

    for name, site in sites_config.sites.items():
        is_default = CHECK_MARK if name == sites_config.default_site else ""
        table.add_row(name, site.domain, is_default)

    console.print(table)
    console.print(
        "[dim italic]To view full site details use[/] [dim bold]anaconda sites show \\[name or domain][/]"
    )


@sites_app.command(name="show")
def sites_show(
    site: Annotated[
        Optional[str],
        typer.Argument(
            help="Choose configured site name or domain name. If unspecified will show the configured default site.",
        ),
    ] = None,
    all: Annotated[
        Optional[bool], typer.Option("--all", help="Show all site configurations")
    ] = False,
    show_hidden: Annotated[bool, typer.Option(help="Show hidden fields")] = False,
) -> None:
    """Show the site configuration for the default site or look up by the provided name or domain."""

    hidden = {
        "api_key",
        "auth_domain_override",
        "client_id",
        "hash_hostname",
        "keyring",
        "preferred_token_storage",
        "login_success_path",
        "login_error_path",
        "openid_config_path",
        "oidc_request_headers",
        "redirect_uri",
    }

    exclude = None if show_hidden else hidden

    if all:
        sites = AnacondaAuthSitesConfig()
        all_sites = {
            config.site: config.model_dump(exclude=exclude)
            for config in sites.sites.root.values()
        }
        console.print_json(data=all_sites)
    else:
        config = AnacondaAuthSitesConfig.load_site(site=site)
        data = config.model_dump(exclude=exclude)
        data = {"site": config.site, **data}
        console.print_json(data=data)


def _confirm_write(
    sites: AnacondaAuthSitesConfig,
    yes: Optional[bool],
    preserve_existing_keys: bool = True,
) -> None:
    if yes is True:
        sites.write_config(preserve_existing_keys=preserve_existing_keys)
    elif yes is False:
        sites.write_config(dry_run=True, preserve_existing_keys=preserve_existing_keys)
    else:
        sites.write_config(dry_run=True, preserve_existing_keys=preserve_existing_keys)
        if Confirm.ask("Confirm:"):
            sites.write_config(preserve_existing_keys=preserve_existing_keys)


def _sites_add_or_modify(
    ctx: typer.Context,
    domain: Annotated[
        Optional[str],
        typer.Option(help="Domain name for site, defaults to 'anaconda.com'"),
    ] = None,
    name: Annotated[
        Optional[str],
        typer.Option(help="Name for site, defaults to domain if not supplied"),
    ] = None,
    default: Annotated[bool, typer.Option(help="Set this site as default")] = False,
    api_key: Annotated[
        Optional[str],
        typer.Option(
            help=f"API key for site. CAUTION: this will get written to {anaconda_config_path()}"
        ),
    ] = None,
    preferred_token_storage: Annotated[Optional[str], typer.Option(hidden=True)] = None,
    auth_domain_override: Annotated[Optional[str], typer.Option(hidden=True)] = None,
    keyring: Annotated[Optional[str], typer.Option(hidden=True)] = None,
    ssl_verify: Annotated[
        Optional[bool], typer.Option("--ssl-verify/--no-ssl-verify")
    ] = None,
    use_truststore: Annotated[
        Optional[bool], typer.Option("--use-truststore/--no-use-truststore")
    ] = None,
    extra_headers: Annotated[
        Optional[str],
        typer.Option(help="Extra headers in JSON format to use for all requests"),
    ] = None,
    client_id: Annotated[Optional[str], typer.Option(hidden=True)] = None,
    redirect_uri: Annotated[Optional[str], typer.Option(hidden=True)] = None,
    openid_config_path: Annotated[Optional[str], typer.Option(hidden=True)] = None,
    oidc_request_headers: Annotated[Optional[str], typer.Option(hidden=True)] = None,
    login_success_path: Annotated[Optional[str], typer.Option(hidden=True)] = None,
    login_error_path: Annotated[Optional[str], typer.Option(hidden=True)] = None,
    use_unified_repo_api_key: Annotated[
        Optional[bool],
        typer.Option("--use-unified-repo-api-key/--no-use-unified-repo-api-key"),
    ] = None,
    hash_hostname: Annotated[
        Optional[bool],
        typer.Option("--hash-host-name/--no-hash-host-name", hidden=True),
    ] = None,
    proxy_servers: Annotated[
        Optional[str], typer.Option(help="JSON string of proxy server mapping")
    ] = None,
    client_cert: Annotated[Optional[str], typer.Option()] = None,
    client_cert_key: Annotated[Optional[str], typer.Option()] = None,
    use_device_flow: Annotated[
        Optional[bool], typer.Option("--use-device-flow/--no-use-device-flow")
    ] = None,
    disable_conda_auto_config: Annotated[
        Optional[bool],
        typer.Option("--disable-conda-auto-config/--no-disable-conda-auto-config"),
    ] = None,
    remove_anaconda_com: Annotated[
        Optional[bool],
        typer.Option(help="Remove the site named 'anaconda.com' if present"),
    ] = True,
    yes: Annotated[
        Optional[bool],
        typer.Option(
            "--yes/--dry-run",
            "-y",
            help="Confirm changes and write, use --dry-run to print diff but do not write",
        ),
    ] = None,
) -> None:
    kwargs: Dict[str, Any] = {}

    if ssl_verify is None and use_truststore is None:
        pass
    elif (ssl_verify or ssl_verify is None) and use_truststore:
        kwargs["ssl_verify"] = "truststore"
    elif ssl_verify is False and use_truststore:
        console.print("Cannot set both --use-truststore and --no-ssl-verify")
        raise typer.Exit(code=ARGUMENT_ERROR)
    elif ssl_verify is False:
        kwargs["ssl_verify"] = False
    else:
        kwargs["ssl_verify"] = True

    if name is not None:
        kwargs["site"] = name
    if domain is not None:
        kwargs["domain"] = domain
    if api_key is not None:
        msg = (
            "[bold yellow]WARNING:[/bold yellow] "
            f"Your API Key will be stored in {anaconda_config_path()} and may not be secure"
        )
        console.print(msg)
        kwargs["api_key"] = api_key
    if extra_headers is not None:
        try:
            parsed_extra_headers = json.loads(extra_headers)
            kwargs["extra_headers"] = parsed_extra_headers
        except json.JSONDecodeError:
            console.print(f"extra-headers={extra_headers} could not be parsed as JSON")
            raise typer.Exit(code=ARGUMENT_ERROR)
    if proxy_servers is not None:
        try:
            parsed_proxy_servers = json.loads(proxy_servers)
            kwargs["proxy_servers"] = parsed_proxy_servers
        except json.JSONDecodeError:
            console.print(f"proxy-servers={proxy_servers} could not be parsed as JSON")
            raise typer.Exit(code=ARGUMENT_ERROR)
    if client_cert is not None:
        kwargs["client_cert"] = client_cert
    if client_cert_key is not None:
        kwargs["client_cert_key"] = client_cert_key
    if use_device_flow is not None:
        kwargs["use_device_flow"] = use_device_flow
    if use_unified_repo_api_key is not None:
        kwargs["use_unified_repo_api_key"] = use_unified_repo_api_key
    if disable_conda_auto_config is not None:
        kwargs["disable_conda_auto_config"] = disable_conda_auto_config
    if preferred_token_storage is not None:
        kwargs["preferred_token_storage"] = preferred_token_storage
    if auth_domain_override is not None:
        kwargs["auth_domain_override"] = auth_domain_override
    if keyring is not None:
        msg = (
            "[bold yellow]WARNING:[/bold yellow] "
            f"Your Keyring contents will be stored in {anaconda_config_path()} and may not be secure"
        )
        console.print(msg)
        try:
            parsed_keyring = json.loads(keyring)
            kwargs["keyring"] = parsed_keyring
        except json.JSONDecodeError:
            console.print("The keyring argument could not be parsed as JSON")
            raise typer.Exit(code=ARGUMENT_ERROR)
    if client_id is not None:
        kwargs["client_id"] = client_id
    if redirect_uri is not None:
        kwargs["redirect_uri"] = redirect_uri
    if openid_config_path is not None:
        kwargs["openid_config_path"] = openid_config_path
    if oidc_request_headers is not None:
        kwargs["oidc_request_headers"] = oidc_request_headers
    if login_success_path is not None:
        kwargs["login_success_path"] = login_success_path
    if login_error_path is not None:
        kwargs["login_error_path"] = login_error_path
    if hash_hostname is not None:
        kwargs["hash_hostname"] = hash_hostname

    sites = AnacondaAuthSitesConfig()

    if ctx.command.name == "add":
        if domain is None:
            console.print("You must supply at least --domain to a add a new site")
            raise typer.Exit(code=ARGUMENT_ERROR)

        if name is None:
            name = domain

        if name in sites.sites:
            console.print(
                f"A site with name {name} already exists, use the modify subcommand to alter it"
            )
            raise typer.Exit(code=PROGRAM_ERROR)

        if remove_anaconda_com and "anaconda.com" in sites.sites.root:
            del sites.sites.root["anaconda.com"]

        config = AnacondaAuthSite(**kwargs)
        sites.add(config, name=config.site)

        if default or len(sites.sites) == 1:
            sites.default_site = config.site

    elif ctx.command.name == "modify":
        if domain is None and name is None:
            console.print(
                "You must supply at least one of --domain or --name to modify a site"
            )
            raise typer.Exit(code=ARGUMENT_ERROR)

        key = sites.sites._find_at(name or domain)
        config = sites.sites.root[key]
        config = config.model_copy(update=kwargs)

        sites.add(config, name=config.site)

        if default:
            sites.default_site = config.site

    _confirm_write(sites, yes)


sites_add = sites_app.command(
    name="add",
    no_args_is_help=True,
    help=f"Add new site configuration to {anaconda_config_path()}",
)(_sites_add_or_modify)

sites_modify = sites_app.command(
    name="modify",
    no_args_is_help=True,
    help=f"Modify site configuration in {anaconda_config_path()}",
)(_sites_add_or_modify)


@sites_app.command(name="remove", no_args_is_help=True)
def sites_remove(
    site: Annotated[str, typer.Argument(help="Site name or domain name to remove.")],
    yes: Annotated[
        Optional[bool],
        typer.Option(
            "--yes/--dry-run",
            "-y",
            help="Confirm changes and write, use --dry-run to print diff but do no write",
        ),
    ] = None,
) -> None:
    """Remove site configuration by name or domain."""
    sites = AnacondaAuthSitesConfig()

    if (
        len(sites.sites) == 1
        and ([site] == list(sites.sites))
        or ([site] == [s.domain for s in sites.sites.values()])
    ):
        console.print(f"{site} is the only configured site and cannot be removed")
        raise typer.Exit(code=PROGRAM_ERROR)

    try:
        config = sites.sites[site]
    except UnknownSiteName as e:
        console.print(e.args[0])
        raise typer.Exit(code=PROGRAM_ERROR)

    sites.remove(site)
    if sites.default_site == config.site:
        sites.default_site = next(iter(sites.sites))

    _confirm_write(sites, yes, preserve_existing_keys=False)
