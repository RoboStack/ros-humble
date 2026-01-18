import logging
import warnings
from importlib.metadata import EntryPoint
from importlib.metadata import entry_points
from sys import version_info
from typing import Dict
from typing import List
from typing import Tuple
from typing import cast

from typer import Typer
from typer.models import DefaultPlaceholder

log = logging.getLogger(__name__)

PLUGIN_GROUP_NAME = "anaconda_cli.subcommand"


def _load_entry_points_for_group(group: str) -> List[Tuple[str, str, Typer]]:
    # The API was changed in Python 3.10, see https://docs.python.org/3/library/importlib.metadata.html#entry-points
    found_entry_points: tuple
    if version_info.major == 3 and version_info.minor <= 9:
        found_entry_points = cast(
            Tuple[EntryPoint, ...], entry_points().get(group, tuple())
        )
    else:
        found_entry_points = tuple(entry_points().select(group=group))  # type: ignore

    loaded = []
    for entry_point in found_entry_points:
        with warnings.catch_warnings():
            # Suppress anaconda-cloud-auth rename warnings just during entrypoint load
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            module: Typer = entry_point.load()
        loaded.append((entry_point.name, entry_point.value, module))

    return loaded


AUTH_HANDLER_ALIASES = {
    "cloud": "anaconda.com",
    "org": "anaconda.org",
}


def load_registered_subcommands(app: Typer) -> None:
    """Load all subcommands from plugins."""
    subcommand_entry_points = _load_entry_points_for_group(PLUGIN_GROUP_NAME)
    auth_handlers: Dict[str, Typer] = {}
    auth_handler_selectors: List[str] = []
    for name, value, subcommand_app in subcommand_entry_points:
        # Allow plugins to disable this if they explicitly want to, but otherwise make True the default
        if isinstance(subcommand_app.info.no_args_is_help, DefaultPlaceholder):
            subcommand_app.info.no_args_is_help = True

        if "login" in [cmd.name for cmd in subcommand_app.registered_commands]:
            auth_handlers[name] = subcommand_app
            alias = AUTH_HANDLER_ALIASES.get(name)
            if alias:
                auth_handlers[alias] = subcommand_app
                auth_handler_selectors.append(alias)

        app.add_typer(subcommand_app, name=name, rich_help_panel="Plugins")

    if auth_handlers:
        auth_handlers_dropdown = sorted(auth_handler_selectors)
        app._load_auth_handlers(  # type: ignore
            auth_handlers=auth_handlers, auth_handlers_dropdown=auth_handlers_dropdown
        )

        log.debug(
            "Loaded subcommand '%s' from '%s'",
            name,
            value,
        )
