# -*- coding: utf8 -*-

"""Package type detection and meta-data extraction."""

from __future__ import annotations

__all__ = ['detect_package_meta', 'detect_package_extension', 'detect_package_type', 'get_attrs']

import collections

import functools

import logging
import tarfile
import typing

from os import path

from binstar_client.utils.config import PackageType
from binstar_client.inspect_package.conda import inspect_conda_package
from binstar_client.inspect_package import conda_installer
from binstar_client.inspect_package.pypi import inspect_pypi_package
from binstar_client.inspect_package.r import inspect_r_package
from binstar_client.inspect_package.ipynb import inspect_ipynb_package
from binstar_client.inspect_package.env import inspect_env_package

if typing.TYPE_CHECKING:
    import typing_extensions

    P = typing_extensions.ParamSpec('P')


logger = logging.getLogger('binstar.detect')


class Meta(typing.NamedTuple):
    """General details on detected package."""

    package_type: PackageType
    extension: str


Raw: typing_extensions.TypeAlias = typing.Optional[str]
OptMeta: typing_extensions.TypeAlias = typing.Optional[Meta]


def checker_for(package_type: PackageType) -> typing.Callable[[typing.Callable[P, Raw]], typing.Callable[P, OptMeta]]:
    """Convert function to a checker for a particular :code:`package_type`."""
    def wrapper(function: typing.Callable[P, Raw]) -> typing.Callable[P, OptMeta]:
        @functools.wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> OptMeta:
            extension: typing.Optional[str] = function(*args, **kwargs)
            if extension is None:
                return None
            return Meta(package_type=package_type, extension=extension)
        return wrapped
    return wrapper


RawDetector: typing_extensions.TypeAlias = typing.Callable[[str], Raw]
Detector: typing_extensions.TypeAlias = typing.Callable[[str], OptMeta]
DETECTORS: typing.Final[typing.OrderedDict[PackageType, Detector]] = collections.OrderedDict()


def detector_for(package_type: PackageType) -> typing.Callable[[RawDetector], Detector]:
    """
    Same as :func:`~checker_for`, but also registers checker in the registry of detectors.

    .. warning::

        All detectors must be defined in the order they must be used to check for a package type.
    """
    def register(function: RawDetector) -> Detector:
        result: Detector = checker_for(package_type)(function)
        if DETECTORS.setdefault(package_type, result) is not result:
            raise ValueError(f'detector for "{package_type.value}" is already registered')
        return result
    return register


def find_postfix(value: str, *options: str) -> typing.Optional[str]:
    """Find a first applicable postfix for a :code:`value` from available :code:`options`."""
    option: str
    for option in options:
        if value.endswith(option):
            return option
    return None


@detector_for(PackageType.CONDA)
def is_conda(filename: str) -> typing.Optional[str]:
    """
    Check if :code:`filename` is a conda package.

    :return: File extension if it is a conda package, otherwise - :code:`None`.
    """
    logger.debug('Testing if %s is a conda package ..', filename)
    if filename.endswith('.conda'):
        return '.conda'
    if filename.endswith('.tar.bz2'):  # Could be a conda package
        try:
            tar_file: tarfile.TarFile
            with tarfile.open(filename, mode='r:bz2') as tar_file:
                tar_file.getmember('info/index.json')
        except KeyError:
            logger.debug("Not a conda package: no 'info/index.json' file in the tarball")
            return None
        logger.debug('This is a conda package')
        return '.tar.bz2'
    logger.debug('Not a conda package (should be a .tar.bz2 or .conda file)')
    return None


@detector_for(PackageType.STANDARD_PYTHON)
def is_pypi(filename: str) -> typing.Optional[str]:
    """
    Check if :code:`filename` is a python package.

    :return: File extension if it is a python package, otherwise - :code:`None`.
    """
    package_type_label: str = PackageType.STANDARD_PYTHON.label
    logger.debug('Testing if %s is a %s package ..', filename, package_type_label)
    if filename.endswith('.whl'):
        logger.debug('This is a %s wheel package', package_type_label)
        return '.whl'
    result: typing.Optional[str] = find_postfix(filename, '.tar.gz', 'tgz')
    if result is None:
        logger.debug('This is not a %s package (expected .tgz, .tar.gz or .whl)', package_type_label)
        return None
    tar_file: tarfile.TarFile
    with tarfile.open(filename) as tar_file:  # Could be a setuptools sdist or r source package
        if any(name.endswith('/PKG-INFO') for name in tar_file.getnames()):
            return result
    logger.debug("This is not a %s package (no '/PKG-INFO' in tarball)", package_type_label)
    return None


@detector_for(PackageType.STANDARD_R)
def is_r(filename: str) -> typing.Optional[str]:
    """
    Check if :code:`filename` is an r package.

    :return: File extension if it is an r package, otherwise - :code:`None`.
    """
    logger.debug('Testing if %s is an R package ..', filename)
    result: typing.Optional[str] = find_postfix(filename, '.tar.gz', 'tgz')
    if result is None:
        logger.debug('This not is an R package (expected .tgz, .tar.gz).')
        return None
    tar_file: tarfile.TarFile
    with tarfile.open(filename) as tar_file:  # Could be a setuptools sdist or r source package
        name: str
        flags: int = 0
        for name in tar_file.getnames():
            if name.endswith('/DESCRIPTION'):
                flags |= 1
            elif name.endswith('/NAMESPACE'):
                flags |= 2
            else:
                continue
            if flags == 3:
                return result
    logger.debug("This not is an R package (no '*/DESCRIPTION' and '*/NAMESPACE' files).")
    return None


@detector_for(PackageType.NOTEBOOK)
def is_ipynb(filename: str) -> typing.Optional[str]:
    """
    Check if :code:`filename` is a notebook.

    :return: File extension if it is a notebook, otherwise - :code:`None`.
    """
    logger.debug('Testing if %s is an ipynb file ..', filename)
    result: typing.Optional[str] = find_postfix(filename, '.ipynb')
    if result is None:
        logger.debug('Not an ipynb file')
    return result


@detector_for(PackageType.ENV)
def is_environment(filename: str) -> typing.Optional[str]:
    """
    Check if :code:`filename` is an environment.

    :return: File extension if it is an environment, otherwise - :code:`None`.
    """
    logger.debug('Testing if %s is an environment file ..', filename)
    result: typing.Optional[str] = find_postfix(filename, '.yml', '.yaml')
    if result is None:
        logger.debug('Not an environment file')
    return result


is_installer: typing.Final[Detector] = (  # pylint: disable=invalid-name
    detector_for(PackageType.INSTALLER)(conda_installer.is_installer)
)


@detector_for(PackageType.PROJECT)
def is_project(filename: str) -> typing.Optional[str]:
    """
    Check if :code:`filename` is a project.

    :return: File extension if it is a project, otherwise - :code:`None`.
    """
    logger.debug('Testing if %s is a project ..', filename)
    if path.isdir(filename):
        return ''
    result: typing.Optional[str] = find_postfix(filename, '.py')
    if result is None:
        logger.debug('Not a project')
    return result


def complete_package_meta(filename: typing.Union[str, bytes], package_type: PackageType) -> OptMeta:
    """Collect package metadata on a :code:`filename` with known :code:`package_type`."""
    if isinstance(filename, bytes):
        filename = filename.decode('utf-8', errors='ignore')

    detector: typing.Optional[Detector] = DETECTORS.get(package_type, None)
    return detector and detector(filename)


def detect_package_meta(filename: typing.Union[str, bytes]) -> OptMeta:
    """Detect package type of a :code:`filename` with additional metadata on it."""
    if isinstance(filename, bytes):
        filename = filename.decode('utf-8', errors='ignore')

    detector: Detector
    result: OptMeta
    for detector in DETECTORS.values():
        if result := detector(filename):
            return result

    return None


def detect_package_extension(filename: typing.Union[str, bytes]) -> typing.Optional[str]:
    """Detect an extension of a package located at :code:`filename`."""
    result: OptMeta = detect_package_meta(filename)
    return result and result.extension


def detect_package_type(filename: typing.Union[str, bytes]) -> typing.Optional[PackageType]:
    """Detect a package type of a :code:`filename`."""
    result: OptMeta = detect_package_meta(filename)
    return result and result.package_type


# ======================================================================================================================

PackageAttributes: typing_extensions.TypeAlias = typing.Dict[str, typing.Any]
ReleaseAttributes: typing_extensions.TypeAlias = typing.Dict[str, typing.Any]
FileAttributes: typing_extensions.TypeAlias = typing.Dict[str, typing.Any]
Attributes: typing_extensions.TypeAlias = typing.Tuple[PackageAttributes, ReleaseAttributes, FileAttributes]


class Inspector(typing.Protocol):  # pylint: disable=too-few-public-methods
    """Common interface for package inspectors."""

    def __call__(self, filename: str, fileobj: typing.BinaryIO, *args: typing.Any, **kwargs: typing.Any) -> Attributes:
        """Collect metadata on a package."""


def inspect_file(filename, fileobj, *args, **kwargs):  # pylint: disable=unused-argument
    """Collect metadata on a generic file."""
    return {}, {'description': ''}, {'basename': path.basename(filename), 'attrs': {}}


INSPECTORS: typing.Final[typing.Mapping[PackageType, Inspector]] = {
    PackageType.CONDA: inspect_conda_package,
    PackageType.STANDARD_PYTHON: inspect_pypi_package,
    PackageType.STANDARD_R: inspect_r_package,
    PackageType.NOTEBOOK: inspect_ipynb_package,
    PackageType.ENV: inspect_env_package,
    PackageType.INSTALLER: conda_installer.inspect_package,
    PackageType.FILE: inspect_file,
}


def get_attrs(package_type: PackageType, filename: str, *args: typing.Any, **kwargs: typing.Any) -> Attributes:
    """Collect metadata attributes on a package."""
    fileobj: typing.BinaryIO
    with open(filename, 'rb') as fileobj:
        return INSPECTORS[package_type](filename, fileobj, *args, **kwargs)
