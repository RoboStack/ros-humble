try:
    from anaconda_cli_base._version import version as __version__
except ImportError:  # pragma: nocover
    __version__ = "unknown"

from anaconda_cli_base.console import init_logging, console

__all__ = ["__version__", "console"]

init_logging()
