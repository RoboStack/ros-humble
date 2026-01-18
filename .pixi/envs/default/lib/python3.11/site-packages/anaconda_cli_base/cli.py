import functools
import os
import sys
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Union
from typing import Sequence
from typing import List

import typer
import click.core
import click.utils
from typer.core import TyperGroup

from anaconda_cli_base import __version__
from anaconda_cli_base import console
from anaconda_cli_base.console import select_from_list
from anaconda_cli_base.plugins import load_registered_subcommands
from anaconda_cli_base.exceptions import ERROR_HANDLERS


class ErrorHandledGroup(TyperGroup):
    def list_commands(self, _: click.core.Context) -> List[str]:
        """Return list of commands in the order they appear on the CLI."""
        return sorted(self.commands, reverse=False)

    def main(  # type: ignore
        self,
        args: Optional[Sequence[str]] = None,
        prog_name: Optional[str] = None,
        complete_var: Optional[str] = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> None:
        try:
            super().main(
                args,
                prog_name,
                complete_var,
                standalone_mode,
                windows_expand_args,
                **extra,
            )
        except Exception as e:
            ctx = self._get_context(args, prog_name, windows_expand_args, **extra)
            if ctx.params.get("verbose", False):
                raise e

            callback = ERROR_HANDLERS[type(e)]
            exit_code = callback(e)
            if exit_code == -1:
                self.main(
                    args,
                    prog_name,
                    complete_var,
                    standalone_mode,
                    windows_expand_args,
                    **extra,
                )
            else:
                cmd = " ".join([*ctx.protected_args, *ctx.args])
                console.print(
                    f"\nTo see a more detailed error message run the command again as"
                    f"\n  [green]anaconda --verbose {cmd}[/green]"
                )
                sys.exit(exit_code)

    def _get_context(
        self,
        args: Optional[Sequence[str]] = None,
        prog_name: Optional[str] = None,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> click.core.Context:
        # This function adapted from typer.TyperGroup._main
        # We need the context to determine if --verbose was requested
        # from the root command.
        if not args:
            args = sys.argv[1:]

            # Covered in Click tests
            if os.name == "nt" and windows_expand_args:  # pragma: no cover
                args = click.utils._expand_args(args)
        else:
            args = list(args)

        if prog_name is None:
            prog_name = click.utils._detect_program_name()

        ctx = self.make_context(prog_name, args, **extra)
        return ctx


app = typer.Typer(
    cls=ErrorHandledGroup,
    add_completion=False,
    help="Welcome to the Anaconda CLI!",
    pretty_exceptions_enable=True,
)


@dataclass()
class ContextExtras:
    """Encapsulates extra information we want to add to the `typer.Context`.

    Used to pass down args from parent CLI to nested subcommands.

    """

    params: Dict[str, Any] = field(default_factory=dict)


@app.callback(invoke_without_command=True, no_args_is_help=True)
def main(
    ctx: typer.Context,
    token: Optional[str] = typer.Option(
        None,
        "-t",
        "--token",
        help="Authentication token to use. A token string or path to a file containing a token",
        hidden=True,
    ),
    site: Optional[str] = typer.Option(
        None,
        "-s",
        "--site",
        help="select the anaconda-client site to use",
        hidden=True,
    ),
    disable_ssl_warnings: Optional[bool] = typer.Option(
        False,
        help="Disable SSL warnings",
        hidden=True,
    ),
    show_traceback: Optional[bool] = typer.Option(
        False,
        help="Show the full traceback for chalmers user errors",
        hidden=True,
    ),
    verbose: Optional[bool] = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Print debug information to the console.",
        hidden=False,
    ),
    quiet: Optional[bool] = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Only show warnings or errors on the console",
        hidden=True,
    ),
    version: Optional[bool] = typer.Option(
        None, "-V", "--version", help="Show version and exit."
    ),
    show_help: Optional[bool] = typer.Option(
        False,
        "-h",
        "--help",
        help="Show this message and exit.",
    ),
) -> None:
    """Anaconda CLI."""
    ctx.obj = ContextExtras()

    # Store all the top-level params on the obj attribute
    ctx.obj.params.update(ctx.params.copy())

    if show_help:
        console.print(ctx.get_help())
        raise typer.Exit()

    if version:
        console.print(
            f"Anaconda CLI, version [cyan]{__version__}[/cyan]",
            style="bold green",
        )
        raise typer.Exit()


def _load_auth_handlers(
    auth_handlers: Dict[str, typer.Typer], auth_handlers_dropdown: List[str]
) -> None:
    def validate_at(ctx: typer.Context, _: Any, choice: str) -> str:
        show_help = ctx.params.get("help", False) is True
        if show_help:
            help_str = ctx.get_help()
            console.print(help_str)
            raise typer.Exit()

        if choice is None:
            if len(auth_handlers_dropdown) > 1:
                choice = select_from_list("choose destination:", auth_handlers_dropdown)
            else:
                # If only one is available, we don't need a picker
                (choice,) = auth_handlers_dropdown

        elif choice not in auth_handlers:
            print(
                f"{choice} is not an allowed value for --at. Use one of {auth_handlers_dropdown}"
            )
            raise typer.Abort()
        return choice

    def _action(
        ctx: typer.Context,
        at: str = typer.Option(
            None, callback=validate_at, help=f"Choose from {auth_handlers_dropdown}"
        ),
        help: bool = typer.Option(False, "--help"),
    ) -> None:
        handler = auth_handlers[at]

        args = ("--help",) if help else ctx.args
        return handler(args=[ctx.command.name, *args], obj=ctx.obj)

    help_doc = {
        "login": "Sign into Anaconda services",
        "logout": "Sign out from Anaconda services",
        "whoami": "Display account information",
    }

    for action in "login", "logout", "whoami":
        decorator = app.command(
            action,
            context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
            rich_help_panel="Authentication",
            help=help_doc[action],
        )
        decorator(_action)


app._load_auth_handlers = _load_auth_handlers  # type: ignore

disable_plugins = bool(os.getenv("ANACONDA_CLI_DISABLE_PLUGINS"))
if not disable_plugins:
    load_registered_subcommands(app)


def _select_main_entrypoint_app(app_: typer.Typer) -> Union[typer.Typer, Callable]:
    """Select the main application to handle the `anaconda` entrypoint at the command line.

    This function, and its execution below at the bottom of this module, can be removed once
    we are fully confident that the `binstar_client.scripts.cli` CLI application (defined
    inside `anaconda-client`) can be replaced with the modern `click`/`typer`-based application.

    If there are no additional plugins registered besides `anaconda-client`, then we fall back
    to the legacy CLI. If any additional plugins are installed, we use the new CLI.

    One can force usage of the legacy CLI by setting the environment variable
    `ANACONDA_CLIENT_FORCE_STANDALONE` to any value (e.g. `1`).

    Users are encouraged to only use the fallback in cases where the new CLI breaks existing usage.
    Please register a bug in that case.

    """
    subcommands = [g.name for g in app_.registered_groups]

    anaconda_client_is_only_plugin = subcommands == ["org"]
    force_new_cli_entrypoint = bool(os.getenv("ANACONDA_CLI_FORCE_NEW"))
    force_legacy_cli_entrypoint = bool(os.getenv("ANACONDA_CLIENT_FORCE_STANDALONE"))
    if force_legacy_cli_entrypoint and force_new_cli_entrypoint:
        raise ValueError(
            "Cannot set both ANACONDA_CLI_FORCE_NEW and ANACONDA_CLIENT_FORCE_STANDALONE at the same time"
        )

    use_legacy_cli_entrypoint = force_legacy_cli_entrypoint or (
        anaconda_client_is_only_plugin and not force_new_cli_entrypoint
    )
    if use_legacy_cli_entrypoint:
        # TODO: We may want to do the conditional import first, and load the subcommand name from anaconda-client
        try:
            from binstar_client.scripts.cli import main
        except ImportError:
            pass
        else:
            return functools.partial(main, allow_plugin_main=False)

    return app_


# Here, we re-assign the global `app` variable based on the selection logic.
# This should be removed once we are confident that we can completely replace the
# `binstar_client` CLI (that inside `anaconda-client`) with the modern
# `click`/`typer`-based application.
app = _select_main_entrypoint_app(app)  # type: ignore
