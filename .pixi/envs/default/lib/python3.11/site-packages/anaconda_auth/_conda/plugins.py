"""Definitions for conda plugins.

This file should not be imported directly, but instead the parent package will
conditionally import it in case conda is not installed in the user's environment.

"""

from typing import Iterable
from typing import Optional

from conda import plugins
from conda.plugins.types import CondaAuthHandler
from conda.plugins.types import CondaSubcommand

from anaconda_auth._conda.auth_handler import AnacondaAuthHandler
from anaconda_auth._conda.conda_token import cli

__all__ = ["conda_subcommands", "conda_auth_handlers"]


def _cli_wrapper(argv: Optional[list[str]] = None) -> int:  # type: ignore
    # If argv is empty tuple, we need to set it back to None
    return cli(argv=argv or None)


@plugins.hookimpl
def conda_subcommands() -> Iterable[CondaSubcommand]:
    """Defines subcommands into conda itself (not `anaconda` CLI)."""
    yield CondaSubcommand(
        name="token",
        summary="Set repository access token and configure default_channels",
        action=_cli_wrapper,  # type: ignore
    )


@plugins.hookimpl
def conda_auth_handlers() -> Iterable[CondaAuthHandler]:
    """Defines the auth handler that can be used for specific channels.

    The following shows an example for how to configure a specific channel inside .condarc:

    ```yaml
    channel_settings:
      - channel: https://repo.anaconda.cloud/*
        auth: anaconda-auth
    ```

    """
    yield CondaAuthHandler(
        name="anaconda-auth",
        handler=AnacondaAuthHandler,
    )
