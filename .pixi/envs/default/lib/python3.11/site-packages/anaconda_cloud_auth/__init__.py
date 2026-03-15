import warnings

from anaconda_auth import __version__ as __version__
from anaconda_auth import client_factory as client_factory
from anaconda_auth import login as login
from anaconda_auth import logout as logout


def warn() -> None:
    warnings.warn(
        "Please replace imports from `import anaconda_cloud_auth` to `import anaconda_auth`",
        DeprecationWarning,
    )


warn()
