# -*- coding: utf8 -*-
# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

from __future__ import annotations

import collections
import enum
import itertools
import logging
import os
import shutil
import stat
import typing
import warnings
from urllib.parse import quote_plus

import yaml
from platformdirs import PlatformDirs

try:
    from conda.gateways import anaconda_client as c_client
except ImportError:
    c_client = None

from binstar_client.errors import BinstarError
from binstar_client.utils import conda, paths
from binstar_client.utils.appdirs import EnvAppDirs
from .yaml import yaml_load, yaml_dump

logger = logging.getLogger('binstar')

if 'BINSTAR_CONFIG_DIR' in os.environ:
    dirs = EnvAppDirs(os.environ['BINSTAR_CONFIG_DIR'])
    USER_CONFIG = os.path.join(dirs.user_config_dir, 'config.yaml')
else:
    dirs = PlatformDirs('binstar', 'ContinuumIO')  # type: ignore
    USER_CONFIG = os.path.join(os.path.expanduser('~'), '.continuum', 'anaconda-client', 'config.yaml')


class PackageType(enum.Enum):
    CONDA = 'conda'
    ENV = 'env'
    FILE = 'file'
    NOTEBOOK = 'ipynb'
    STANDARD_PYTHON = 'pypi'
    STANDARD_R = 'r'
    PROJECT = 'project'
    INSTALLER = 'installer'

    @property
    def label(self) -> str:
        return PACKAGE_TYPE_LABELS.get(self, self.value)

    @classmethod
    def _missing_(cls, value: typing.Any) -> PackageType:
        try:
            return cls(PACKAGE_TYPE_ALIASES[value])
        except KeyError:
            return super()._missing_(value)


PACKAGE_TYPE_ALIASES: typing.Final[typing.Mapping[str, str]] = {
    'PyPI': 'pypi',
    'standard_python': 'pypi',

    'cran': 'r',
    'standard_r': 'r',
}
PACKAGE_TYPE_LABELS: typing.Final[typing.Mapping[PackageType, str]] = {
    PackageType.ENV: 'Environment',
    PackageType.NOTEBOOK: 'Notebook',
    PackageType.CONDA: 'Conda',
    PackageType.STANDARD_PYTHON: 'Standard Python',
    PackageType.STANDARD_R: 'Standard R',
}

USER_LOGDIR: typing.Final[str] = dirs.user_log_dir
SITE_CONFIG: typing.Final[str] = os.path.join(conda.CONDA_ROOT or '/', 'etc', 'anaconda-client', 'config.yaml')
SYSTEM_CONFIG: typing.Final[str] = SITE_CONFIG

DEFAULT_URL = 'https://api.anaconda.org'
DEFAULT_CONFIG = {
    'sites': {
        'anaconda': {'url': DEFAULT_URL},
        'binstar': {'url': DEFAULT_URL},
    },
    'auto_register': True,
    'default_site': None,
    'url': DEFAULT_URL,
    'ssl_verify': True
}

CONFIGURATION_KEYS = [
    'auto_register',
    'default_site',
    'upload_user',
    'sites',
    'url',
    'verify_ssl',
    'ssl_verify',
]

SEARCH_PATH = (
    dirs.site_data_dir,
    '/etc/anaconda-client/',
    '$CONDA_ROOT/etc/anaconda-client/',
    dirs.user_config_dir,
    '~/.continuum/anaconda-client/',
    '$CONDA_PREFIX/etc/anaconda-client/',
)


def recursive_update(config, update_dict):
    for update_key, updated_value in update_dict.items():
        if isinstance(updated_value, typing.Mapping):
            updated_value_dict = recursive_update(config.get(update_key, {}), updated_value)
            config[update_key] = updated_value_dict
        else:
            config[update_key] = update_dict[update_key]

    return config


def get_server_api(token=None, site=None, cls=None, config=None, **kwargs):
    """Get the anaconda server api class."""
    if not cls:
        from binstar_client import Binstar  # pylint: disable=import-outside-toplevel,cyclic-import

        cls = Binstar

    config = config if config is not None else get_config(site=site)

    url = config.get('url', DEFAULT_URL)

    logger.info('Using Anaconda API: %s', url)

    if token:
        logger.debug('Using token from command line args')
    elif 'BINSTAR_API_TOKEN' in os.environ:
        logger.debug('Using token from environment variable BINSTAR_API_TOKEN')
        token = os.environ['BINSTAR_API_TOKEN']
    elif 'ANACONDA_API_TOKEN' in os.environ:
        logger.debug('Using token from environment variable ANACONDA_API_TOKEN')
        token = os.environ['ANACONDA_API_TOKEN']
    else:
        token = load_token(url)

    verify = config.get('ssl_verify', None)
    if verify is None:
        verify = config.get('verify_ssl', None)
    if verify is None:
        verify = True

    return cls(token, domain=url, verify=verify, **kwargs)


def get_binstar(args=None, cls=None):
    """
    DEPRECATED METHOD,

    use `get_server_api`
    """

    warnings.warn(
        'method get_binstar is deprecated, please use `get_server_api`',
        DeprecationWarning
    )

    token = getattr(args, 'token', None)
    log_level = getattr(args, 'log_level', logging.INFO)
    site = getattr(args, 'site', None)

    aserver_api = get_server_api(token=token, site=site, log_level=log_level, cls=cls)
    return aserver_api


TOKEN_DIRS = [
    dirs.user_config_dir,
    os.path.join(os.path.dirname(USER_CONFIG), 'tokens'),
]
TOKEN_DIR = TOKEN_DIRS[-1]
if c_client is not None:
    conda_token_dir = c_client._get_binstar_token_directory()  # pylint: disable=W0212
    if conda_token_dir != TOKEN_DIRS[0]:
        warnings.warn(
            'conda and anaconda-client have conflicting token paths:\n'
            '  conda: %s\n'
            '  anaconda-client: %s\n'
            'to ensure consistent behavior, the conda path will be used.\n' % (conda_token_dir, TOKEN_DIR),
            RuntimeWarning
        )
        TOKEN_DIRS.insert(0, conda_token_dir)


def store_token(token, args):
    config = get_config(site=args and args.site)
    url = config.get('url', DEFAULT_URL)
    if c_client is not None:
        logger.debug('Using conda..set_binstar_token')
        c_client.set_binstar_token(url, token)
        return

    for token_dir in TOKEN_DIRS:
        if not os.path.isdir(token_dir):
            os.makedirs(token_dir)
        tokenfile = os.path.join(token_dir, '%s.token' % quote_plus(url))

        if os.path.isfile(tokenfile):
            os.unlink(tokenfile)
        with open(tokenfile, 'w') as file:  # pylint: disable=unspecified-encoding
            file.write(token)
        os.chmod(tokenfile, stat.S_IWRITE | stat.S_IREAD)


def load_token(url):
    if c_client is not None:
        logger.debug('Using conda..read_binstar_tokens')
        url_c = url.rstrip('/') + '/'
        for binstar_url, token in c_client.read_binstar_tokens().items():
            if url_c.startswith(binstar_url.rstrip('/') + '/'):
                if token:
                    return token

    for token_dir in TOKEN_DIRS:
        tokenfile = os.path.join(token_dir, '%s.token' % quote_plus(url))

        if os.path.isfile(tokenfile):
            logger.debug('Found login token: %s', tokenfile)
            with open(tokenfile) as file:  # pylint: disable=unspecified-encoding
                token = file.read().strip()

            if token:
                return token

            logger.debug('Token file is empty: %s', tokenfile)
            logger.debug('Removing file: %s', tokenfile)
            os.unlink(tokenfile)

    return None


def remove_token(args):
    config = get_config(site=args and args.site)
    url = config.get('url', DEFAULT_URL)

    for token_dir in TOKEN_DIRS:
        tokenfile = os.path.join(token_dir, '%s.token' % quote_plus(url))
        if os.path.isfile(tokenfile):
            os.unlink(tokenfile)


def load_config(config_file):
    data = {}
    warn_msg = None

    try:
        with open(config_file) as file:  # pylint: disable=unspecified-encoding
            data = yaml_load(file) or data
    except yaml.YAMLError:
        backup_file = config_file + '.bak'
        shutil.copyfile(config_file, backup_file)
        warn_msg = 'Config file `{}` has invalid structure and couldn\'t be read. \n' \
                   'File content was backed up to `{}`'.format(config_file, backup_file)
    except PermissionError:
        warn_msg = 'Not enough rights to access config file `{}`! Please review file permissions.'.format(config_file)
    except OSError as error:
        logger.exception(error)

    if warn_msg is not None:
        warnings.warn(warn_msg)

    return data


def load_file_configs(search_path):
    def _file_yaml_loader(fullpath):
        assert (fullpath.endswith('.yml')  # nosec
                or fullpath.endswith('.yaml') or fullpath.endswith('anacondarc')), fullpath
        yield fullpath, load_config(fullpath)

    def _dir_yaml_loader(fullpath):
        for filename in os.listdir(fullpath):
            if filename.endswith('.yml') or filename.endswith('.yaml'):
                filepath = os.path.join(fullpath, filename)
                yield filepath, load_config(filepath)

    # map a stat result to a file loader or a directory loader
    _loader = {
        stat.S_IFREG: _file_yaml_loader,
        stat.S_IFDIR: _dir_yaml_loader,
    }

    def _get_st_mode(path):
        # stat the path for file type, or None if path doesn't exist
        try:
            return stat.S_IFMT(os.stat(path).st_mode)
        except OSError:
            return None

    expanded_paths = list(map(paths.normalize, search_path))
    stat_paths = (
        _get_st_mode(path)
        for path in expanded_paths
    )
    load_paths = (
        _loader[st_mode](path)
        for path, st_mode in zip(expanded_paths, stat_paths)
        if st_mode is not None
    )
    raw_data = collections.OrderedDict(
        kv
        for kv in itertools.chain.from_iterable(load_paths)
    )

    return raw_data


def get_config(site=None):
    config = DEFAULT_CONFIG.copy()

    file_configs = load_file_configs(SEARCH_PATH)
    for file_name in file_configs:
        recursive_update(config, file_configs[file_name])

    site = site or config.get('default_site')
    sites = config.get('sites', {})

    if site:
        site = str(site)

        if site not in sites:
            logger.warning('Site alias "%s" does not exist in the config file', site)
        else:
            # This takes whatever keys are set for the site into the top level of the config dict
            recursive_update(config, sites.get(site, {}))

    return config


def save_config(data, config_file):
    try:
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        temp_file = config_file + '~'
        with open(temp_file, 'w') as stream:  # pylint: disable=unspecified-encoding
            yaml_dump(data, stream=stream)

        os.replace(temp_file, config_file)

    except (OSError, yaml.YAMLError) as error:
        raise BinstarError("Config file `{}` couldn't be saved! Changes may be lost.".format(config_file)) from error


def set_config(data, user=True):
    warnings.warn('Use save_config instead of set_config', DeprecationWarning)
    save_config(data, USER_CONFIG if user else SYSTEM_CONFIG)
