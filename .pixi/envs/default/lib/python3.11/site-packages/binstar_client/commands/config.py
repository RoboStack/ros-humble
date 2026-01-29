# pylint: disable=missing-function-docstring

"""
anaconda-client configuration

Get, Set, Remove or Show the anaconda-client configuration.

###### anaconda-client sites

anaconda-client sites are a mechanism to allow users to quickly switch
between Anaconda repository instances. This is primarily used for testing
the anaconda alpha site. But also has applications for the
on-site [Anaconda Enterprise](http://continuum.io/anaconda-server).

anaconda-client comes with two pre-configured sites `alpha` and
`binstar` you may use these in one of two ways:

  * Invoke the anaconda command with the `-s/--site` option
    e.g. to use the alpha testing site:

        anaconda -s alpha whoami

  * Set a site as the default:

        anaconda config --set default_site alpha
        anaconda whoami

###### Add a anaconda-client site

After installing [Anaconda Enterprise](http://continuum.io/anaconda-server)
you can add a site named **site_name** like this:

    anaconda config --set sites.site_name.url "http://<anaconda-enterprise-ip>:<port>/api"
    anaconda config --set default_site site_name

###### Site Options VS Global Options

All options can be set as global options - affecting all sites,
or site options - affecting only one site

By default options are set globally e.g.:

    anaconda config --set OPTION VALUE

If you want the option to be limited to a single site,
prefix the option with `sites.site_name` e.g.

    anaconda config --set sites.site_name.OPTION VALUE

###### Common anaconda-client configuration options

  * `url`: Set the anaconda api url (default: https://api.anaconda.org)
  * `ssl_verify`: Perform ssl validation on the https requests.
    ssl_verify may be `True`, `False` or a path to a root CA pem file.


###### Toggle auto_register when doing anaconda upload

The default is yes, automatically create a new package when uploading.
If no, then an upload will fail if the package name does not already exist on the server.

    anaconda config --set auto_register yes|no

"""

from __future__ import print_function

import logging
from argparse import RawDescriptionHelpFormatter

from binstar_client.errors import ShowHelp
from binstar_client.utils.config import (SEARCH_PATH, USER_CONFIG, SYSTEM_CONFIG, CONFIGURATION_KEYS,
                                         get_config, save_config, load_config, load_file_configs)
from ..utils.yaml import yaml_dump, safe_load

logger = logging.getLogger('binstar.config')

DEPRECATED = {
    'verify_ssl': 'Please use ssl_verify instead'
}


def recursive_set(config_data, key, value, type_):
    while '.' in key:
        prefix, key = key.split('.', 1)
        config_data = config_data.setdefault(prefix, {})

    if key not in CONFIGURATION_KEYS:
        logger.warning('"%s" is not a known configuration key', key)

    if key in DEPRECATED:
        message = '{} is deprecated: {}'.format(key, DEPRECATED[key])
        logger.warning(message)

    config_data[key] = type_(value)


def recursive_remove(config_data, key):
    while '.' in key:
        if not config_data:
            return
        prefix, key = key.split('.', 1)
        config_data = config_data.get(prefix, {})

    del config_data[key]


def main(args):
    config = get_config()

    if args.show:
        logger.info(yaml_dump(config))
        return

    if args.show_sources:
        config_files = load_file_configs(SEARCH_PATH)
        for path in config_files:
            logger.info('==> %s <==', path)
            logger.info(yaml_dump(config_files[path]))
        return

    if args.get:
        if args.get in config:
            logger.info(config[args.get])
        else:
            logger.info("The value of '%s' is not set.", args.get)
        return

    if args.files:
        logger.info('User Config: %s', USER_CONFIG)
        logger.info('System Config: %s', SYSTEM_CONFIG)
        return

    config_file = USER_CONFIG if args.user else SYSTEM_CONFIG

    config = load_config(config_file)

    for key, value in args.set:
        recursive_set(config, key, value, args.type)

    for key in args.remove:
        try:
            recursive_remove(config, key)
        except KeyError:
            logger.error('Key %s does not exist', key)

    if not (args.set or args.remove):
        raise ShowHelp()

    save_config(config, config_file)


def add_parser(subparsers):
    description = 'Anaconda client configuration'
    parser = subparsers.add_parser('config',
                                   help=description,
                                   description=description,
                                   epilog=__doc__,
                                   formatter_class=RawDescriptionHelpFormatter)

    parser.add_argument('--type', default=safe_load,
                        help='The type of the values in the set commands')

    agroup = parser.add_argument_group('actions')

    agroup.add_argument('--set', nargs=2, action='append', default=[],
                        help='sets a new variable: name value', metavar=('name', 'value'))
    agroup.add_argument('--get', metavar='name',
                        help='get value: name')
    agroup.add_argument('--remove', action='append', default=[],
                        help='removes a variable')
    agroup.add_argument('--show', action='store_true', default=False,
                        help='show all variables')
    agroup.add_argument('-f', '--files', action='store_true',
                        help='show the config file names')
    agroup.add_argument('--show-sources', action='store_true',
                        help='Display all identified config sources')
    lgroup = parser.add_argument_group('location')
    lgroup.add_argument('-u', '--user', action='store_true', dest='user', default=True,
                        help='set a variable for this user')
    lgroup.add_argument('-s', '--system', '--site', action='store_false', dest='user',
                        help='set a variable for all users on this machine')

    parser.set_defaults(main=main, sub_parser=parser)
