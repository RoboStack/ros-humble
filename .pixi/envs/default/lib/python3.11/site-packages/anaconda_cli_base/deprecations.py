# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Reusable helpers for deprecating functionality.

Note: most of this file has been copied from conda's implementation. Usage
documentation can be found here: https://docs.conda.io/projects/conda/en/latest/dev-guide/deprecations.html

"""

from __future__ import annotations

import sys
import warnings
from argparse import Action
from functools import wraps
from types import ModuleType
from typing import TYPE_CHECKING

from anaconda_cli_base import __version__

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from typing import Any, Callable, TypeVar
    from typing_extensions import ParamSpec, Self

    from packaging.version import Version

    T = TypeVar("T")
    P = ParamSpec("P")

    ActionType = TypeVar("ActionType", bound=type[Action])


class DeprecatedError(RuntimeError):
    pass


# inspired by deprecation (https://deprecation.readthedocs.io/en/latest/) and
# CPython's warnings._deprecated
class DeprecationHandler:
    _version: str | None
    _version_tuple: tuple[int, ...] | None
    _version_object: Version | None

    def __init__(self: Self, version: str) -> None:
        """Factory to create a deprecation handle for the specified version.

        Args:
            version: The version to compare against when checking deprecation statuses.

        """
        self._version = version
        # Try to parse the version string as a simple tuple[int, ...] to avoid
        # packaging.version import and costlier version comparisons.
        self._version_tuple = self._get_version_tuple(version)
        self._version_object = None

    @staticmethod
    def _get_version_tuple(version: str) -> tuple[int, ...] | None:
        """Return version as non-empty tuple of ints if possible, else None.

        Args:
            version: Version string to parse.

        """
        try:
            return tuple(int(part) for part in version.strip().split(".")) or None
        except (AttributeError, ValueError):
            return None

    def _version_less_than(self: Self, version: str) -> bool:
        """Test whether own version is less than the given version.

        Args:
            version: Version string to compare against.

        """
        if self._version_tuple and (version_tuple := self._get_version_tuple(version)):
            return self._version_tuple < version_tuple

        # If self._version or version could not be represented by a simple
        # tuple[int, ...], do a more elaborate version parsing and comparison.
        # Avoid this import otherwise to reduce import time.
        from packaging.version import parse

        if self._version_object is None:
            try:
                self._version_object = parse(self._version)  # type: ignore[arg-type]
            except TypeError:
                # TypeError: self._version could not be parsed
                self._version_object = parse("0.0.0.dev0+placeholder")
        return self._version_object < parse(version)

    def __call__(
        self: Self,
        deprecate_in: str,
        remove_in: str,
        *,
        addendum: str | None = None,
        stack: int = 0,
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Deprecation decorator for functions, methods, & classes.

        Args:
            deprecate_in: Version in which code will be marked as deprecated.
            remove_in: Version in which code is expected to be removed.
            addendum: Optional additional messaging. Useful to indicate what to do instead.
            stack: Optional stacklevel increment.

        """

        def deprecated_decorator(func: Callable[P, T]) -> Callable[P, T]:
            # detect function name and generate message
            category, message = self._generate_message(
                deprecate_in=deprecate_in,
                remove_in=remove_in,
                prefix=f"{func.__module__}.{func.__qualname__}",
                addendum=addendum,
            )

            # alert developer that it's time to remove something
            if not category:
                raise DeprecatedError(message)

            # alert user that it's time to remove something
            @wraps(func)
            def inner(*args: P.args, **kwargs: P.kwargs) -> T:
                warnings.warn(message, category, stacklevel=2 + stack)

                return func(*args, **kwargs)

            return inner

        return deprecated_decorator

    def argument(
        self: Self,
        deprecate_in: str,
        remove_in: str,
        argument: str,
        *,
        rename: str | None = None,
        addendum: str | None = None,
        stack: int = 0,
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Deprecation decorator for keyword arguments.

        Args:
            deprecate_in: Version in which code will be marked as deprecated.
            remove_in: Version in which code is expected to be removed.
            argument: The argument to deprecate.
            rename: Optional new argument name.
            addendum: Optional additional messaging. Useful to indicate what to do instead.
            stack: Optional stacklevel increment.

        """

        def deprecated_decorator(func: Callable[P, T]) -> Callable[P, T]:
            # detect function name and generate message
            category, message = self._generate_message(
                deprecate_in=deprecate_in,
                remove_in=remove_in,
                prefix=f"{func.__module__}.{func.__qualname__}({argument})",
                # provide a default addendum if renaming and no addendum is provided
                addendum=(
                    f"Use '{rename}' instead." if rename and not addendum else addendum
                ),
            )

            # alert developer that it's time to remove something
            if not category:
                raise DeprecatedError(message)

            # alert user that it's time to remove something
            @wraps(func)
            def inner(*args: P.args, **kwargs: P.kwargs) -> T:
                # only warn about argument deprecations if the argument is used
                if argument in kwargs:
                    warnings.warn(message, category, stacklevel=2 + stack)

                    # rename argument deprecations as needed
                    value = kwargs.pop(argument, None)
                    if rename:
                        kwargs.setdefault(rename, value)

                return func(*args, **kwargs)

            return inner

        return deprecated_decorator

    def action(
        self: Self,
        deprecate_in: str,
        remove_in: str,
        action: ActionType,
        *,
        addendum: str | None = None,
        stack: int = 0,
    ) -> ActionType:
        """Wraps any argparse.Action to issue a deprecation warning."""

        class DeprecationMixin(Action):
            category: type[Warning]
            help: str  # override argparse.Action's help type annotation

            def __init__(inner_self: Self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)

                category, message = self._generate_message(
                    deprecate_in=deprecate_in,
                    remove_in=remove_in,
                    prefix=(
                        # option_string are ordered shortest to longest,
                        # use the longest as it's the most descriptive
                        f"`{inner_self.option_strings[-1]}`"
                        if inner_self.option_strings
                        # if not a flag/switch, use the destination itself
                        else f"`{inner_self.dest}`"
                    ),
                    addendum=addendum,
                    deprecation_type=FutureWarning,
                )

                # alert developer that it's time to remove something
                if not category:
                    raise DeprecatedError(message)

                inner_self.category = category
                inner_self.help = message

            def __call__(
                inner_self: Self,
                parser: ArgumentParser,
                namespace: Namespace,
                values: Any,
                option_string: str | None = None,
            ) -> None:
                # alert user that it's time to remove something
                warnings.warn(
                    inner_self.help,
                    inner_self.category,
                    stacklevel=7 + stack,
                )

                super().__call__(parser, namespace, values, option_string)

        return type(action.__name__, (DeprecationMixin, action), {})  # type: ignore[return-value]

    def module(
        self: Self,
        deprecate_in: str,
        remove_in: str,
        *,
        addendum: str | None = None,
        stack: int = 0,
    ) -> None:
        """Deprecation function for modules.

        Args:
            deprecate_in: Version in which code will be marked as deprecated.
            remove_in: Version in which code is expected to be removed.
            addendum: Optional additional messaging. Useful to indicate what to do instead.
            stack: Optional stacklevel increment.

        """
        self.topic(
            deprecate_in=deprecate_in,
            remove_in=remove_in,
            topic=self._get_module(stack)[1],
            addendum=addendum,
            stack=2 + stack,
        )

    def constant(
        self: Self,
        deprecate_in: str,
        remove_in: str,
        constant: str,
        value: Any,
        *,
        addendum: str | None = None,
        stack: int = 0,
    ) -> None:
        """Deprecation function for module constant/global.

        Args:
            deprecate_in: Version in which code will be marked as deprecated.
            remove_in: Version in which code is expected to be removed.
            constant:
            value:
            addendum: Optional additional messaging. Useful to indicate what to do instead.
            stack: Optional stacklevel increment.

        """
        # detect calling module
        module, fullname = self._get_module(stack)
        # detect function name and generate message
        category, message = self._generate_message(
            deprecate_in=deprecate_in,
            remove_in=remove_in,
            prefix=f"{fullname}.{constant}",
            addendum=addendum,
        )

        # alert developer that it's time to remove something
        if not category:
            raise DeprecatedError(message)

        # patch module level __getattr__ to alert user that it's time to remove something
        super_getattr = getattr(module, "__getattr__", None)

        def __getattr__(name: str) -> Any:
            if name == constant:
                warnings.warn(message, category, stacklevel=2 + stack)
                return value

            if super_getattr:
                return super_getattr(name)

            raise AttributeError(f"module '{fullname}' has no attribute '{name}'")

        module.__getattr__ = __getattr__  # type: ignore[method-assign]

    def topic(
        self: Self,
        deprecate_in: str,
        remove_in: str,
        *,
        topic: str,
        addendum: str | None = None,
        stack: int = 0,
    ) -> None:
        """Deprecation function for a topic.

        Args:
            deprecate_in: Version in which code will be marked as deprecated.
            remove_in: Version in which code is expected to be removed.
            topic: The topic being deprecated.
            addendum: Optional additional messaging. Useful to indicate what to do instead.
            stack: Optional stacklevel increment.

        """
        # detect function name and generate message
        category, message = self._generate_message(
            deprecate_in=deprecate_in,
            remove_in=remove_in,
            prefix=topic,
            addendum=addendum,
        )

        # alert developer that it's time to remove something
        if not category:
            raise DeprecatedError(message)

        # alert user that it's time to remove something
        warnings.warn(message, category, stacklevel=2 + stack)

    def _get_module(self: Self, stack: int) -> tuple[ModuleType, str]:
        """Detect the module from which we are being called.

        Args:
            stack: The stacklevel increment.

        Returns:
            The module and module name.

        """
        try:
            frame = sys._getframe(2 + stack)
        except IndexError:
            # IndexError: 2 + stack is out of range
            pass
        else:
            # Shortcut finding the module by manually inspecting loaded modules.
            try:
                filename = frame.f_code.co_filename
            except AttributeError:
                # AttributeError: frame.f_code.co_filename is undefined
                pass
            else:
                for loaded in sys.modules.values():
                    if not isinstance(loaded, ModuleType):
                        # sys.modules typed as Iterable of ModuleType
                        continue  # type: ignore
                    if not hasattr(loaded, "__file__"):
                        continue
                    if loaded.__file__ == filename:
                        return (loaded, loaded.__name__)

            # If above failed, do an expensive import and costly getmodule call.
            import inspect

            module = inspect.getmodule(frame)
            if module is not None:
                return (module, module.__name__)

        raise DeprecatedError("unable to determine the calling module")

    def _generate_message(
        self: Self,
        deprecate_in: str,
        remove_in: str,
        prefix: str,
        addendum: str | None,
        *,
        deprecation_type: type[Warning] = DeprecationWarning,
    ) -> tuple[type[Warning] | None, str]:
        """Generate the standardized deprecation message and determine whether the
        deprecation is pending, active, or past.

        Args:
            deprecate_in: Version in which code will be marked as deprecated.
            remove_in: Version in which code is expected to be removed.
            prefix: The message prefix, usually the function name.
            addendum: Additional messaging. Useful to indicate what to do instead.
            deprecation_type: The warning type to use for active deprecations.

        Returns:
            The warning category (if applicable) and the message.

        """
        category: type[Warning] | None
        if self._version_less_than(deprecate_in):
            category = PendingDeprecationWarning
            warning = f"is pending deprecation and will be removed in {remove_in}."
        elif self._version_less_than(remove_in):
            category = deprecation_type
            warning = f"is deprecated and will be removed in {remove_in}."
        else:
            category = None
            warning = f"was slated for removal in {remove_in}."

        return (
            category,
            " ".join(filter(None, [prefix, warning, addendum])),  # message
        )


deprecated: DeprecationHandler = DeprecationHandler(__version__)
