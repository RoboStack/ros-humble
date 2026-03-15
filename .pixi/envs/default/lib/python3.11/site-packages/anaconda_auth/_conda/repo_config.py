"""
Configure Conda to use Anaconda Commercial Edition.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import warnings
from os.path import abspath
from os.path import expanduser
from os.path import join
from typing import Any
from urllib.parse import urljoin

import conda
import conda.gateways.logging  # noqa: F401
from conda.base import context as context_module
from conda.cli import main as conda_main
from conda.exceptions import CondaKeyError
from conda.gateways.anaconda_client import read_binstar_tokens
from conda.gateways.anaconda_client import remove_binstar_token
from conda.gateways.anaconda_client import set_binstar_token
from conda.gateways.connection.session import CondaSession
from conda.models.channel import Channel
from packaging import version
from rich.prompt import Confirm

from anaconda_auth._conda.conda_api import Commands
from anaconda_auth._conda.condarc import CondaRC
from anaconda_auth._conda.config import _build_channel_settings
from anaconda_cli_base import console

CONDA_VERSION = version.parse(conda.__version__)

REPO_URL = os.getenv("CONDA_TOKEN_REPO_URL", "https://repo.anaconda.cloud/repo/")
MAIN_CHANNEL = "main"
ACTIVE_CHANNELS = ["r", "msys2"]
ARCHIVE_CHANNELS = ["free", "mro-archive", "pro"]

user_rc_path = abspath(expanduser("~/.condarc"))
escaped_user_rc_path = user_rc_path.replace("%", "%%")
escaped_sys_rc_path = abspath(join(sys.prefix, ".condarc")).replace("%", "%%")


def run_command(*args: Any, **kwargs: Any) -> int:
    with warnings.catch_warnings():
        # Ignore PendingDeprecationWarning from any other plugins invoked when calling conda
        warnings.simplefilter("ignore", PendingDeprecationWarning)
        return conda_main(*args, **kwargs)


class CondaTokenError(RuntimeError):
    pass


class CondaVersionWarning(UserWarning):
    pass


def _get_condarc_args(
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> list[str]:
    """Construct conda CLI args related to condarc location."""
    config_args = []

    if condarc_system:
        config_args.append("--system")
    elif condarc_env:
        config_args.append("--env")
    elif condarc_file:
        config_args.append(f"--file={condarc_file}")

    return config_args


def can_restore_free_channel() -> bool:
    # restore_free_channel was removed in conda 25.9.0
    return CONDA_VERSION >= version.parse("4.7.0") and CONDA_VERSION < version.parse(
        "25.9.0"
    )


def clean_index() -> None:
    """Runs conda clean -i.

    It is important to remove index cache when
    changing the condarc to ensure that the downloaded
    repodata is correct.
    """
    run_command(Commands.CLEAN, "-i", "-y", "-q")


def validate_token(token: str, no_ssl_verify: bool = False) -> None:
    """Checks that token can be used with the repository."""

    # Force ssl_verify: false
    if no_ssl_verify:
        context_module.context.ssl_verify = False  # type: ignore

    # Use CondaSession to be compatible with ssl_verify: truststore
    # https://conda.io/projects/conda/en/latest/user-guide/configuration/settings.html#ssl-verify-ssl-verification
    # Clear metaclass cache to create new session checking ssl_verify
    if hasattr(CondaSession, "cache_clear"):
        # not present in conda < January 2024
        CondaSession.cache_clear()
    else:
        # what cache_clear() does
        try:
            CondaSession._thread_local.sessions.clear()  # type: ignore
        except AttributeError:
            # AttributeError: thread's session cache has not been initialized
            pass

    session = CondaSession()

    # Ensure the index cache is cleaned first
    clean_index()

    channel = Channel(urljoin(REPO_URL, "main/noarch/repodata.json"))
    channel.token = token
    token_url = str(channel.url(with_credentials=True))

    r = session.head(token_url, verify=session.verify)
    if r.status_code != 200:
        raise CondaTokenError(
            "The token could not be validated. Please check that you have typed it correctly."
        )


def configure_plugin(should_set_default_channels: bool = False) -> None:
    """Configure the user's .condarc file with the anaconda-auth plugin.

    We install the auth-handler plugin by writing the "channel_settings" key and associate
    all premium repo channels with this auth handler.

    """
    settings = _build_channel_settings(include_defaults=False)
    if not settings:
        return
    condarc = CondaRC()
    condarc.backup()
    for s in settings:
        condarc.update_channel_settings(s["channel"], s["auth"], username=None)
    condarc.save()


def enable_extra_safety_checks(
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> None:
    """Enable package signature verification.

    This will set extra_safety_checks: True and
    signing_metadata_url_base in the CondaRC file.
    """
    if CONDA_VERSION < version.parse("4.10.1"):
        warnings.warn(
            "You need upgrade to at least Conda version 4.10.1 to enable package signature verification.",
            CondaVersionWarning,
        )
        return

    condarc_file_args = _get_condarc_args(
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )

    safety_check_args = ["--set", "extra_safety_checks", "true"]
    safety_check_args.extend(condarc_file_args)
    run_command(Commands.CONFIG, *safety_check_args)

    metadata_url_args = ["--set", "signing_metadata_url_base", REPO_URL.rstrip("/")]
    metadata_url_args.extend(condarc_file_args)
    run_command(Commands.CONFIG, *metadata_url_args)


def disable_extra_safety_checks(
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> None:
    """Disable package signature verification.

    This will set extra_safety_checks: false and remove
    signing_metadata_url_base in the CondaRC file.
    """

    if CONDA_VERSION < version.parse("4.10.1"):
        return

    condarc_file_args = _get_condarc_args(
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )

    safety_check_args = ["--set", "extra_safety_checks", "false"]
    safety_check_args.extend(condarc_file_args)
    try:
        run_command(Commands.CONFIG, *safety_check_args)
    except CondaKeyError:
        pass

    metadata_url_args = ["--remove-key", "signing_metadata_url_base"]
    metadata_url_args.extend(condarc_file_args)
    try:
        run_command(Commands.CONFIG, *metadata_url_args)
    except CondaKeyError:
        pass


def _set_add_anaconda_token(
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> None:
    """Run conda config --set add_anaconda_token true.

    Setting this parameter to true ensures that the token
    is used when making requests to the repository.
    """
    config_args = ["--set", "add_anaconda_token", "true"]

    condarc_file_args = _get_condarc_args(
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )
    config_args.extend(condarc_file_args)

    run_command(Commands.CONFIG, *config_args)


def _set_ssl_verify_false(
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> None:
    """Run conda config --set ssl_verify false.

    Setting this parameter to false disables all
    SSL verification for conda activities
    """
    config_args = ["--set", "ssl_verify", "false"]

    condarc_file_args = _get_condarc_args(
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )
    config_args.extend(condarc_file_args)

    run_command(Commands.CONFIG, *config_args)


def _unset_restore_free_channel(
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> None:
    """Runs conda config --set restore_free_channel false.

    The free channel is provided by Commercial Edition as
    and should be added directly."""
    config_args = ["--set", "restore_free_channel", "false"]

    condarc_file_args = _get_condarc_args(
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )
    config_args.extend(condarc_file_args)

    run_command(Commands.CONFIG, *config_args, use_exception_handler=True)


def _set_channel(
    channel: str,
    prepend: bool = True,
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> None:
    """Adds a named Commercial Edition channel to default_channels."""
    channel_url = urljoin(REPO_URL, channel)

    config_args = [
        "--prepend" if prepend else "--append",
        "default_channels",
        channel_url,
    ]

    condarc_file_args = _get_condarc_args(
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )
    config_args.extend(condarc_file_args)

    run_command(Commands.CONFIG, *config_args)


def _get_from_condarc(
    key: str,
    default: Any = None,
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> Any:
    """Retrieve the existing default_channels from the user's `.condarc` file.

    If the user does not have a "default_channels" section, an empty list is returned.

    """
    config_args = ["--get", key, "--json"]

    condarc_file_args = _get_condarc_args(
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )
    config_args.extend(condarc_file_args)

    # Capture the JSON output from stdout
    string_io = io.StringIO()
    with contextlib.redirect_stdout(string_io):
        run_command(Commands.CONFIG, *config_args)

    try:
        result = json.loads(string_io.getvalue())
    except json.JSONDecodeError:
        result = {}

    return result.get("get", {}).get(key, default)


def _get_default_channels(
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> list[str]:
    """Retrieve the existing default_channels from the user's `.condarc` file.

    If the user does not have a "default_channels" section, an empty list is returned.

    """
    return _get_from_condarc(
        "default_channels",
        default=[],
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )


def _remove_default_channels(
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
) -> None:
    """Runs conda config --remove-key default_channels

    It is best to remove the default_channels in case they
    are not set at the default values before configuring
    Commercial Edition.
    """
    config_args = ["--remove-key", "default_channels"]

    condarc_file_args = _get_condarc_args(
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )
    config_args.extend(condarc_file_args)

    # We suppress a CondaKeyError below to prevent logging an internal conda error
    # to the terminal.
    err_io = io.StringIO()
    with contextlib.redirect_stderr(err_io):
        try:
            run_command(Commands.CONFIG, *config_args)
        except CondaKeyError:
            pass

    err_string = err_io.getvalue()
    if "CondaKeyError" not in err_string.strip():
        print(err_string, file=sys.stderr)


def _prompt_to_set_default_channels() -> bool:
    """Prompt the user for whether they would like to set their default channels."""
    existing_default_channels = _get_default_channels()
    if existing_default_channels:
        console.print("Existing default channels found:")
        for c in existing_default_channels:
            console.print(f"- {c}")
        console.print(
            "This action will override the existing default_channels setting."
        )
    else:
        console.print("Prepared to set default channels in .condarc.")

    return Confirm.ask("Proceed?", default=False)


def configure_default_channels(
    condarc_system: bool = False,
    condarc_env: bool = False,
    condarc_file: str | None = None,
    include_archive_channels: list[str] | None = None,
    force: bool = False,
) -> None:
    """Configure the default_channels to utilize only Commercial Edition.


    This function performs the following actions
    1. unset default_channels if it exists in the condarc
    2. unset restore_free_channel if it exists in the condarc
    3. Add the main, r, and msys2 channels to default_channels
    4. Optionally add any of the archive channels:
       free, pro, mro, mro-archive
    """
    console.print("Configuring your [cyan].condarc[/cyan] file")

    existing_default_channels = _get_default_channels()

    existing_default_channels_short_names = [
        c.removeprefix(REPO_URL) for c in existing_default_channels
    ]
    if set(existing_default_channels_short_names) == set(
        [MAIN_CHANNEL] + ACTIVE_CHANNELS
    ):
        console.print("Default channels already configured, nothing to do.")
        return

    if not (force or _prompt_to_set_default_channels()):
        return

    _remove_default_channels(condarc_system, condarc_env, condarc_file)

    if can_restore_free_channel() and _get_from_condarc(
        "restore_free_channel",
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    ):
        _unset_restore_free_channel(condarc_system, condarc_env, condarc_file)

    _set_channel(
        MAIN_CHANNEL,
        prepend=True,
        condarc_system=condarc_system,
        condarc_env=condarc_env,
        condarc_file=condarc_file,
    )

    for c in ACTIVE_CHANNELS:
        _set_channel(
            c,
            prepend=False,
            condarc_system=condarc_system,
            condarc_env=condarc_env,
            condarc_file=condarc_file,
        )

    if include_archive_channels is None:
        return

    for c in include_archive_channels:
        if c in ARCHIVE_CHANNELS:
            _set_channel(
                c,
                prepend=False,
                condarc_system=condarc_system,
                condarc_env=condarc_env,
                condarc_file=condarc_file,
            )
        else:
            raise ValueError(
                f"The archive channel {c} is not one of {', '.join(ARCHIVE_CHANNELS)}"
            )


def token_list() -> dict[str, str]:
    """Return a dictionary of tokens for all configured repository urls.

    Note that this function will return tokens configured for non-Commercial Edition
    urls."""
    return read_binstar_tokens()


def token_remove(
    system: bool = False, env: bool = False, file: str | None = None
) -> None:
    """Completely remove the Commercial Edition token and default_channels.

    This function performs three actions.
    1. Remove the token
    2. Remove the custom default_channels in the condarc
    3. Disable package signature verification
    4. Run conda clean -i
    """
    remove_binstar_token(REPO_URL)
    _remove_default_channels(system, env, file)
    disable_extra_safety_checks(system, env, file)
    clean_index()


def token_set(
    token: str,
    system: bool = False,
    env: bool = False,
    file: str | None = None,
    include_archive_channels: list[str] | None = None,
    no_ssl_verify: bool = False,
    enable_signature_verification: bool = False,
    force: bool = False,
) -> None:
    """Set the Commercial Edition token and configure default_channels.


    This function performs 4 actions.
    1. Remove previous Commercial Edition token if present.
    2. Add token.
    3. Configure default_channels in the condarc file.
    4. Optionally enable Conda package signature verification
    5. Run conda clean -i
    """
    remove_binstar_token(REPO_URL)

    set_binstar_token(REPO_URL, token)
    _set_add_anaconda_token(system, env, file)

    if no_ssl_verify:
        _set_ssl_verify_false(system, env, file)

    if enable_signature_verification:
        enable_extra_safety_checks(system, env, file)

    configure_default_channels(system, env, file, include_archive_channels, force=force)
    clean_index()
