# -*- coding: utf8 -*-

"""

    anaconda upload CONDA_PACKAGE_1.tar.bz2

See Also:

* Uploading a Conda Package: https://docs.anaconda.com/free/anacondaorg/user-guide/packages/conda-packages/#cloud-uploading-conda-packages
* Uploading a Standard Python Package: https://docs.anaconda.com/free/anacondaorg/user-guide/packages/standard-python-packages/#uploading-stdpython-packages

"""  # noqa: E501, pylint: disable=line-too-long

from __future__ import annotations

__all__ = ['add_parser']

import argparse
import glob
import itertools
import logging
import os
import typing

import binstar_client
from binstar_client import errors
from binstar_client.deprecations import DEPRECATION_MESSAGE_NOTEBOOKS_PROJECTS_ENVIRONMENTS_REMOVED
from binstar_client.utils import bool_input, DEFAULT_CONFIG, get_config, get_server_api
from binstar_client.utils.config import PackageType
from binstar_client.utils import detect
from binstar_client.utils import projects

if typing.TYPE_CHECKING:
    import typing_extensions


KeyT = typing.TypeVar('KeyT')
CacheRecordT = typing.TypeVar('CacheRecordT', bound='CacheRecord')

PackageKey: typing_extensions.TypeAlias = str
ReleaseKey: typing_extensions.TypeAlias = typing.Tuple[str, str]


logger = logging.getLogger('binstar.upload')


def main(arguments: argparse.Namespace) -> None:
    """Entrypoint of the :code:`upload` command."""
    uploader: Uploader = Uploader(arguments=arguments)
    uploader.api.check_server()
    _ = uploader.username

    try:
        filename: str
        for filename in sorted(set(itertools.chain.from_iterable(arguments.files))):
            uploader.upload(filename)
    finally:
        uploader.print_uploads()
        uploader.cleanup()


class UploadedPackage(typing.TypedDict):
    """General details on a package successfully uploaded to a server."""

    package_type: PackageType
    username: str
    name: str
    version: str
    basename: str
    url: str


class CacheRecord:  # pylint: disable=too-few-public-methods
    """Common interface for cached server records."""

    __slots__ = ('empty',)

    def __init__(self, empty: bool = True) -> None:
        """Initialize new :class:`~CacheRecord` instance."""
        self.empty: bool = empty

    @staticmethod
    def cleanup(
            storage: typing.Dict[KeyT, CacheRecordT],
            action: typing.Optional[typing.Callable[[KeyT, CacheRecordT], typing.Any]] = None,
    ) -> int:
        """
        Remove all empty records from :code:`storage`.

        Optional :code:`action` function might be called for each instance being removed.
        """
        to_remove: typing.List[KeyT] = []

        key: KeyT
        record: CacheRecordT
        for key, record in storage.items():
            if record.empty:
                to_remove.append(key)
                if action is not None:
                    action(key, record)

        for key in to_remove:
            storage.pop(key)

        return len(to_remove)


class PackageCacheRecord(CacheRecord):
    """Cached details on a package stored on a server."""

    __slots__ = ('name', 'package_types')

    def __init__(self, name: str, empty: bool = True, package_types: typing.Iterable[PackageType] = ()) -> None:
        """Initialize new :class:`~PackageCacheRecord` instance."""
        super().__init__(empty=empty)
        self.name: typing.Final[str] = name
        self.package_types: typing.List[PackageType] = list(package_types)

    def update(self, package_type: PackageType) -> None:
        """Update record after a file is uploaded to this package."""
        self.empty = False
        if package_type not in self.package_types:
            self.package_types.append(package_type)


class ReleaseCacheRecord(CacheRecord):
    """Cached details on a release stored on a server."""

    __slots__ = ('name', 'version')

    def __init__(self, name: str, version: str, empty: bool = True) -> None:
        """Initialize new :class:`~ReleaseCacheRecord` instance."""
        super().__init__(empty=empty)
        self.name: typing.Final[str] = name
        self.version: typing.Final[str] = version

    def update(self) -> None:
        """Update record after a file is uploaded to this release."""
        self.empty = False


class PackageMeta:
    """Collected details on a package file being currently uploaded."""

    __slots__ = (
        'filename', 'meta',
        '__file_attrs', '__name', '__package_attrs', '__release_attrs', '__version',
    )

    def __init__(self, filename: str, meta: detect.Meta) -> None:
        """Initialize new :class:`~PackageMeta` instance."""
        self.filename: typing.Final[str] = filename
        self.meta: typing.Final[detect.Meta] = meta

        self.__file_attrs: typing.Optional[detect.FileAttributes] = None
        self.__name: typing.Optional[str] = None
        self.__package_attrs: typing.Optional[detect.PackageAttributes] = None
        self.__release_attrs: typing.Optional[detect.ReleaseAttributes] = None
        self.__version: typing.Optional[str] = None

    @property
    def extension(self) -> str:  # noqa: D401
        """File extension of the package file."""
        return self.meta.extension

    @property
    def file_attrs(self) -> detect.FileAttributes:  # noqa: D401
        """Attributes of a file being uploaded."""
        if self.__file_attrs is None:
            self._update_attrs()
        return typing.cast(detect.FileAttributes, self.__file_attrs)

    @property
    def name(self) -> str:  # noqa: D401
        """Name of a package for which file is being uploaded."""
        if self.__name is None:
            self._update_name()
        return typing.cast(str, self.__name)

    @name.setter
    def name(self, value: str) -> None:
        """Update value of a :attr:`~PackageMeta.name`."""
        self._update_name(value)

    @property
    def package_attrs(self) -> detect.PackageAttributes:  # noqa: D401
        """Attributes of a package for which file is being uploaded."""
        if self.__package_attrs is None:
            self._update_attrs()
        return typing.cast(detect.PackageAttributes, self.__package_attrs)

    @property
    def package_key(self) -> PackageKey:  # noqa: D401
        """Key for accessing related cached package record."""
        return self.name

    @property
    def package_type(self) -> PackageType:  # noqa: D401
        """Type of a package being uploaded."""
        return self.meta.package_type

    @property
    def release_attrs(self) -> detect.ReleaseAttributes:  # noqa: D401
        """Attributes of a release for which file is being uploaded."""
        if self.__release_attrs is None:
            self._update_attrs()
        return typing.cast(detect.ReleaseAttributes, self.__release_attrs)

    @property
    def release_key(self) -> ReleaseKey:  # noqa: D401
        """Key for accessing related cached release record."""
        return self.name, self.version

    @property
    def version(self) -> str:  # noqa: D401
        """Version of a package being uploaded."""
        if self.__version is None:
            self._update_version()
        return typing.cast(str, self.__version)

    @version.setter
    def version(self, value: str) -> None:
        """Update value of a :attr:`~PackageMeta.version`."""
        self._update_version(value)

    def rebuild_basename(self) -> str:
        """
        Rebuild package basename from its attributes.

        Usually basename contains actual filename being uploaded, which may not include expected metadata in the
        expected format. This function allows to enforce the standard without requiring user to rename the file.

        :return: New basename.
        """
        subdir: typing.Optional[str] = self.file_attrs.setdefault('attrs', {}).get('subdir', None)
        if not subdir:
            try:
                subdir, _ = self.file_attrs.get('basename', '').split('/', 1)
            except ValueError:
                subdir = 'noarch'
            self.file_attrs['attrs']['subdir'] = subdir

        build: str = self.file_attrs['attrs'].setdefault('build', '0')

        self.file_attrs['basename'] = f'{subdir}/{self.name}-{self.version}-{build}{self.extension}'
        return self.file_attrs['basename']

    def _update_attrs(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        """Update content of all attribute fields."""
        logger.info('Extracting %s attributes for upload', self.package_type.label.lower())
        try:
            self.__package_attrs, self.__release_attrs, self.__file_attrs = detect.get_attrs(
                self.package_type, self.filename, *args, **kwargs,
            )
        except Exception as error:
            message: str = (
                f'Trouble reading metadata from "{self.filename}". '
                f'Is this a valid {self.package_type.label.lower()} package?'
            )
            logger.error(message)
            raise errors.BinstarError(message) from error

    def _update_name(self, value: typing.Optional[str] = None) -> None:
        """Update value of a :attr:`~PackageMeta.name`."""
        name: str = self.package_attrs.get('name', '')

        if value:
            if name:
                good_names: typing.List[str] = [name := name.lower()]
                if self.package_type is PackageType.STANDARD_PYTHON:
                    good_names.append(name.replace('-', '_'))
                if value.lower() not in good_names:
                    message: str = (
                        f'Package name on the command line "{value.lower()}" '
                        f'does not match the package name in the file "{self.package_attrs["name"].lower()}"'
                    )
                    logger.error(message)
                    raise errors.BinstarError(message)
            name = value

        elif not name:
            message = (
                f'Could not detect package name for package type {self.package_type.label.lower()}, '
                f'please use the --package option'
            )
            logger.error(message)
            raise errors.BinstarError(message)

        self.__name = name

    def _update_version(self, value: typing.Optional[str] = None) -> None:
        """Update value of a :attr:`~PackageMeta.version`."""
        if not value:
            value = self.release_attrs.get('version', None)
            if not value:
                message: str = (
                    f'Could not detect package version for package type "{self.package_type.label.lower()}", '
                    f'please use the --version option'
                )
                logger.error(message)
                raise errors.BinstarError(message)

        self.__version = value


class Uploader:  # pylint: disable=too-many-instance-attributes
    """Manager for package and project uploads."""

    __slots__ = (
        'arguments', 'uploaded_packages', 'uploaded_projects',
        '__api', '__config', '__username',
        '__package_cache', '__release_cache',
    )

    def __init__(self, arguments: argparse.Namespace) -> None:
        """Initialize new :class:`~Uploader` instance."""
        self.arguments: typing.Final[argparse.Namespace] = arguments
        self.uploaded_packages: typing.Final[typing.List[UploadedPackage]] = []
        self.uploaded_projects: typing.Final[typing.List[projects.UploadedProject]] = []

        self.__api: typing.Optional[binstar_client.Binstar] = None
        self.__config: typing.Optional[typing.Mapping[str, typing.Any]] = None
        self.__username: typing.Optional[str] = None

        self.__package_cache: typing.Final[typing.Dict[PackageKey, PackageCacheRecord]] = {}
        self.__release_cache: typing.Final[typing.Dict[ReleaseKey, ReleaseCacheRecord]] = {}

    @property
    def api(self) -> binstar_client.Binstar:  # noqa: D401
        """Client used to access anaconda.org API."""
        if self.__api is None:
            self.__api = get_server_api(token=self.arguments.token, site=self.arguments.site, config=self.config)
        return self.__api

    @property
    def config(self) -> typing.Mapping[str, typing.Any]:  # noqa: D401
        """Configuration of the :code:`anaconda-client`."""
        if self.__config is None:
            self.__config = get_config(site=self.arguments.site)
        return self.__config

    @property
    def username(self) -> str:  # noqa: D401
        """Name of the user or organization to upload packages and projects to."""
        if self.__username is None:
            details: str = ''
            username: str = self.arguments.user or ''
            if (not username) and (username := self.config.get('upload_user', '')):
                details = ' (from "upload_user" preference)'
            if username:
                try:
                    self.api.user(username)
                except errors.NotFound as error:
                    message: str = f'User "{username}" does not exist{details}'
                    logger.error(message)
                    raise errors.BinstarError(message) from error
            else:
                username = self.api.user()['login']
            logger.info('Using "%s" as upload username%s', username, details)
            self.__username = username
        return self.__username

    def cleanup(self) -> None:
        """
        Remove empty releases and packages.

        Package or release considered to be empty if it was created to upload files to, but all file uploads failed.
        """
        def remove_empty_release(_key: ReleaseKey, record: ReleaseCacheRecord) -> None:
            try:
                if not self.api.release(self.username, record.name, record.version).get('distributions', []):
                    logger.info('Removing empty "%s/%s" release after failed upload', record.name, record.version)
                    self.api.remove_release(self.username, record.name, record.version)
            except (AttributeError, TypeError, errors.NotFound):
                pass

        def remove_empty_package(_key: PackageKey, record: PackageCacheRecord) -> None:
            try:
                if not self.api.package(self.username, record.name).get('files', []):
                    logger.info('Removing empty "%s" package after failed upload', record.name)
                    self.api.remove_package(self.username, record.name)
            except (AttributeError, TypeError, errors.NotFound):
                pass

        CacheRecord.cleanup(self.__release_cache, remove_empty_release)
        CacheRecord.cleanup(self.__package_cache, remove_empty_package)

    def get_package(self, meta: PackageMeta, *, force: bool = False) -> PackageCacheRecord:
        """
        Retrieve details on a package from the server.

        If not forced - may return cached record.
        """
        key: typing.Final[PackageKey] = meta.package_key
        cache_record: typing.Optional[PackageCacheRecord]
        if (not force) and (cache_record := self.__package_cache.get(key, None)):
            return cache_record

        try:
            instance: typing.Mapping[str, typing.Any] = self.api.package(self.username, meta.name)
            cache_record = PackageCacheRecord(
                name=meta.name,
                empty=False,
                package_types=list(map(PackageType, instance.get('package_types', ())))
            )
        except errors.NotFound as error:
            if not self.arguments.auto_register:
                message: str = (
                    f'Anaconda repository package {self.username}/{meta.name} does not exist. '
                    f'Please run "anaconda package --create" to create this package namespace in the cloud.'
                )
                logger.error(message)
                raise errors.UserError(message) from error

            summary: typing.Optional[str] = self.arguments.summary
            if (summary is None) and ((summary := meta.package_attrs.get('summary', None)) is None):
                message = (
                    f'Could not detect package summary for package type {meta.package_type.label.lower()}, '
                    f'please use the --summary option'
                )
                logger.error(message)
                raise errors.BinstarError(message) from error

            self.api.add_package(
                self.username,
                meta.name,
                summary,
                meta.package_attrs.get('license'),
                public=not self.arguments.private,
                attrs=meta.package_attrs,
                license_url=meta.package_attrs.get('license_url'),
                license_family=meta.package_attrs.get('license_family'),
                package_type=meta.package_type,
            )
            cache_record = PackageCacheRecord(name=meta.name, empty=True, package_types=[])

        self.__package_cache[key] = cache_record
        return cache_record

    def get_release(self, meta: PackageMeta, *, force: bool = False) -> ReleaseCacheRecord:
        """
        Retrieve details on a release from the server.

        If not forced - may return cached record.
        """
        key: typing.Final[ReleaseKey] = meta.release_key
        cache_record: typing.Optional[ReleaseCacheRecord]
        if (not force) and (cache_record := self.__release_cache.get(key, None)):
            return cache_record

        try:
            self.api.release(self.username, meta.name, meta.version)
            if self.arguments.force_metadata_update:
                self.api.update_release(self.username, meta.name, meta.version, meta.release_attrs)
            cache_record = ReleaseCacheRecord(name=meta.name, version=meta.version, empty=False)
        except errors.NotFound:
            announce: typing.Optional[str] = None
            if self.arguments.mode == 'interactive':
                logger.info('The release "%s/%s/%s" does not exist', self.username, meta.name, meta.version)
                if not bool_input('Would you like to create it now?'):
                    logger.info('good-bye')
                    raise SystemExit(-1) from None

                logger.info('Announcements are emailed to your package followers.')
                if bool_input('Would you like to make an announcement to the package followers?', False):
                    announce = input('Markdown Announcement:\n')

            self.api.add_release(self.username, meta.name, meta.version, [], announce, meta.release_attrs)
            cache_record = ReleaseCacheRecord(name=meta.name, version=meta.version, empty=True)

        self.__release_cache[key] = cache_record
        return cache_record

    def print_uploads(self) -> None:
        """Print details on all successful package and project uploads."""
        package_info: UploadedPackage
        for package_info in self.uploaded_packages:
            logger.info('%s located at:\n  %s\n', package_info['package_type'].label.lower(), package_info['url'])

        project_info: projects.UploadedProject
        for project_info in self.uploaded_projects:
            logger.info('Project %s uploaded to:\n  %s\n', project_info['name'], project_info['url'])

    def upload(self, filename: str) -> bool:
        """Upload a file to the server."""
        if not os.path.exists(filename):
            message: str = f'File "{filename}" does not exist'
            logger.error(message)
            raise errors.BinstarError(message)
        logger.info('Processing "%s"', filename)

        package_meta: detect.Meta = self.detect_package_meta(
            filename,
            package_type=self.arguments.package_type and PackageType(self.arguments.package_type),
        )

        if package_meta.package_type is PackageType.PROJECT:
            return self.upload_project(filename)
        return self.upload_package(filename, package_meta)

    def upload_package(self, filename: str, package_meta: detect.Meta) -> bool:
        """Upload a package to the server."""
        if package_meta.package_type is PackageType.NOTEBOOK:
            logger.error(DEPRECATION_MESSAGE_NOTEBOOKS_PROJECTS_ENVIRONMENTS_REMOVED)
            return False

        meta: PackageMeta = PackageMeta(filename=filename, meta=package_meta)
        meta._update_attrs(parser_args=self.arguments)  # pylint: disable=protected-access
        meta._update_name(self.arguments.package)  # pylint: disable=protected-access
        meta._update_version(self.arguments.version)  # pylint: disable=protected-access
        if self.arguments.build_id is not None:
            meta.file_attrs.setdefault('attrs', {})['binstar_build'] = self.arguments.build_id
        if self.arguments.summary is not None:
            meta.release_attrs['summary'] = self.arguments.summary
        if self.arguments.description is not None:
            meta.release_attrs['description'] = self.arguments.description
        if (meta.package_type is PackageType.CONDA) and (not self.arguments.keep_basename):
            meta.rebuild_basename()

        if not self._check_file(meta):
            return False

        logger.info('Creating package "%s"', meta.name)
        package: PackageCacheRecord = self.get_package(meta)
        if not self.validate_package_type(package, meta.package_type):
            return False

        logger.info('Creating release "%s"', meta.version)
        self.get_release(meta)

        logger.info('Uploading file "%s/%s/%s/%s"', self.username, meta.name, meta.version, meta.file_attrs['basename'])
        return self._upload_file(meta)

    def upload_project(self, filename: str) -> bool:
        """Upload a project to the server."""
        uploaded_project: projects.UploadedProject = projects.upload_project(filename, self.arguments, self.username)
        self.uploaded_projects.append(uploaded_project)
        return True

    def _check_file(self, meta: PackageMeta) -> bool:
        """"""
        basename: str = meta.file_attrs['basename']
        try:
            self.api.distribution(self.username, meta.name, meta.version, basename)
        except errors.NotFound:
            return True

        if self.arguments.mode == 'skip':
            logger.info('Distribution already exists. Skipping upload.\n')
            return False

        if self.arguments.mode == 'force':
            logger.warning('Distribution "%s" already exists. Removing.', basename)
            self.api.remove_dist(self.username, meta.name, meta.version, basename)
            return True

        if self.arguments.mode == 'interactive':
            if bool_input(f'Distribution "{basename}" already exists. Would you like to replace it?'):
                self.api.remove_dist(self.username, meta.name, meta.version, basename)
                return True
            logger.info('Not replacing distribution "%s"', basename)
            return False

        logger.info(
            (
                'Distribution already exists. '  # pylint: disable=implicit-str-concat
                'Please use the -i/--interactive or --force or --skip options or `anaconda remove %s/%s/%s/%s`'
            ),
            self.username, meta.name, meta.version, basename,
        )
        raise errors.Conflict(f'file {basename} already exists for package {meta.name} version {meta.version}', 409)

    def _upload_file(self, meta: PackageMeta) -> bool:
        """Perform upload of a file after its metadata and related package and release are prepared."""
        basename: str = meta.file_attrs['basename']
        package_type: typing.Union[PackageType, str] = meta.file_attrs.pop('binstar_package_type', meta.package_type)

        stream: typing.BinaryIO
        with open(meta.filename, 'rb') as stream:
            result: typing.Mapping[str, typing.Any] = self.api.upload(
                self.username,
                meta.name,
                meta.version,
                basename,
                stream,
                package_type,
                self.arguments.description,
                dependencies=meta.file_attrs.get('dependencies'),
                attrs=meta.file_attrs['attrs'],
                channels=self.arguments.labels,
            )

        self.uploaded_packages.append({
            'package_type': meta.package_type,
            'username': self.username,
            'name': meta.name,
            'version': meta.version,
            'basename': basename,
            'url': result.get('url', f'https://anaconda.org/{self.username}/{meta.name}'),
        })
        self.__package_cache[meta.package_key].update(meta.package_type)
        self.__release_cache[meta.release_key].update()
        logger.info('Upload complete\n')
        return True

    @staticmethod
    def detect_package_meta(filename: str, package_type: typing.Optional[PackageType] = None) -> detect.Meta:
        """Detect primary details on package being uploaded."""
        if package_type is None:
            logger.info('Detecting file type...')
            result: detect.OptMeta = detect.detect_package_meta(filename)
            if result is None:
                message: str = (
                    f'Could not detect package type of file {filename!r} '
                    f'please specify package type with option --package-type'
                )
                logger.error(message)
                raise errors.BinstarError(message)
            logger.info('File type is "%s"', result.package_type.label)
        else:
            result = detect.complete_package_meta(filename, package_type)
            if result is None:
                result = detect.Meta(package_type=package_type, extension=os.path.splitext(filename)[1])
        return result

    @staticmethod
    def validate_package_type(package: PackageCacheRecord, package_type: PackageType) -> bool:
        """Check if file of :code:`package_type` might be uploaded to :code:`package`."""
        if not package.package_types:
            return True

        if package_type in package.package_types:
            return True

        group: typing.Set[PackageType]
        for group in [{PackageType.CONDA, PackageType.STANDARD_PYTHON}]:
            if (not group.isdisjoint(package.package_types)) and (package_type in group):
                return True

        message: str = (
            f'You already have a {package.package_types[0].label.lower()} named "{package.name}". '
            f'Use a different name for this {package_type.label.lower()}.'
        )
        logger.error(message)
        raise errors.BinstarError(message)


def pathname_list(item: str) -> typing.List[str]:
    """Expand file patterns to lists of actual file names."""
    if (os.name == 'nt') and any(character in '*?' for character in item):
        return glob.glob(item)
    return [item]


def add_parser(subparsers: typing.Any) -> None:
    """Register an :code:`upload` command in the application."""
    description: str = 'Upload packages to your Anaconda repository'
    parser: argparse.ArgumentParser = subparsers.add_parser(
        'upload',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help=description, description=description,
        epilog=__doc__,
    )

    parser.add_argument('files', nargs='+', help='Distributions to upload', default=[], type=pathname_list)

    label_help: str = (
        '{deprecation}Add this file to a specific {label}. '
        'Warning: if the file {label}s do not include "main", '
        'the file will not show up in your user {label}'
    )

    parser.add_argument(
        '-c', '--channel',
        action='append',
        default=[],
        dest='labels',
        help=label_help.format(deprecation='[DEPRECATED]\n', label='channel'),
        metavar='CHANNELS',
    )
    parser.add_argument(
        '-l', '--label',
        action='append',
        dest='labels',
        help=label_help.format(deprecation='', label='label'),
    )
    parser.add_argument(
        '--no-progress',
        help="Don't show upload progress",
        action='store_true',
    )
    parser.add_argument(
        '-u', '--user',
        help='User account or Organization, defaults to the current user',
    )
    parser.add_argument(
        '--keep-basename',
        dest='keep_basename',
        help=(
            'Do not normalize a basename when uploading a conda package. '
            'Note: this parameter only applies to conda, and not standard Python packages.'
        ),
        action='store_true'
    )

    mgroup = parser.add_argument_group('metadata options')
    mgroup.add_argument(
        '-p', '--package',
        help='Defaults to the package name in the uploaded file',
    )
    mgroup.add_argument(
        '-v', '--version',
        help='Defaults to the package version in the uploaded file',
    )
    mgroup.add_argument(
        '-s', '--summary',
        help='Set the summary of the package',
    )
    mgroup.add_argument(
        '-t', '--package-type',
        help='Set the package type. Defaults to autodetect',
    )
    mgroup.add_argument(
        '-d', '--description',
        help='description of the file(s)',
    )
    mgroup.add_argument(
        '--thumbnail',
        help="Notebook's thumbnail image",
    )
    mgroup.add_argument(
        '--private',
        help='Create the package with private access',
        action='store_true',
    )

    register_group = parser.add_mutually_exclusive_group()
    register_group.add_argument(
        '--no-register',
        dest='auto_register',
        action='store_false',
        help="Don't create a new package namespace if it does not exist",
    )
    register_group.add_argument(
        '--register',
        dest='auto_register',
        action='store_true',
        help='Create a new package namespace if it does not exist',
    )

    parser.set_defaults(auto_register=DEFAULT_CONFIG.get('auto_register', True))
    parser.add_argument(
        '--build-id',
        help='Anaconda repository Build ID (internal only)',
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-i', '--interactive',
        action='store_const',
        help='Run an interactive prompt if any packages are missing',
        dest='mode',
        const='interactive',
    )
    group.add_argument(
        '-f', '--fail',
        help='Fail if a package or release does not exist (default)',
        action='store_const',
        dest='mode',
        const='fail',
    )
    group.add_argument(
        '--force',
        help='Force a package upload regardless of errors',
        action='store_const',
        dest='mode',
        const='force',
    )
    group.add_argument(
        '--skip-existing',
        help='Skip errors on package batch upload if it already exists',
        action='store_const',
        dest='mode',
        const='skip',
    )
    group.add_argument(
        '-m', '--force-metadata-update',
        action='store_true',
        help='Overwrite existing release metadata with the metadata from the package.',
    )

    parser.set_defaults(main=main)
