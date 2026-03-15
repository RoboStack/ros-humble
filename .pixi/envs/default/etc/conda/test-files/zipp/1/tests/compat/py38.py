import sys

if (3, 9) <= sys.version_info < (3, 11):  # pragma: no cover
    from importlib.abc import Traversable  # type: ignore[attr-defined, unused-ignore]
elif sys.version_info < (3, 9):  # pragma: no cover
    from importlib_resources.abc import Traversable


__all__ = ['Traversable']
