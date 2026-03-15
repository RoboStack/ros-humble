try:
    from anaconda_auth._version import version as __version__
except ImportError:  # pragma: no cover
    __version__ = "unknown"

from anaconda_auth.actions import login  # noqa: E402
from anaconda_auth.actions import logout  # noqa: E402
from anaconda_auth.client import client_factory  # noqa: E402

__all__ = ["__version__", "login", "logout", "client_factory"]
