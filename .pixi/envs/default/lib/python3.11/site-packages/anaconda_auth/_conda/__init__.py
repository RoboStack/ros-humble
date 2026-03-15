"""This module provides conda plugins.

Since conda is not a strict dependency of `anaconda-auth`, the modules here should
NOT be imported outside of this module. This package is declared as the plugin entrypoint
inside `pyproject.toml` such that it will be imported and, if conda is installed, the
plugin definitions will be imported. However, if conda is not installed, no plugins are
imported into the runtime.

As a result, we do not have to spread conditional imports everywhere, but we do need to
be careful that only the single top-level import of this subpackage is performed.

"""
