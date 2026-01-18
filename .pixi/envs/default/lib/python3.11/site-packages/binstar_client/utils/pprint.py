# pylint: disable=missing-class-docstring,missing-function-docstring

"""
Created on Aug 8, 2013

@author: sean
"""

from __future__ import unicode_literals

import logging

from dateutil.parser import parse as parse_date

from binstar_client.utils import config

logger = logging.getLogger('binstar.pprint')

fmt_access = (  # pylint: disable=invalid-name
    '     %(full_name)-32s | %(latest_version)8s | %(access)-12s | %(package_types)-17s | %(conda_platforms)-15s | ' +
    '%(builds)-10s'
)
fmt_no_access = (  # pylint: disable=invalid-name
    '     %(full_name)-32s | %(latest_version)8s | %(package_types)-17s | %(conda_platforms)-15s | %(builds)-10s'
)


def pprint_orgs(orgs):
    logger.info('Organizations:')
    for org in orgs:
        logger.info('   + %(login)25s', org)


def pprint_package_header(access=True, revisions=False):
    package_header = {
        'full_name': 'Name',
        'access': 'Access',
        'package_types': 'Package Types',
        'latest_version': 'Version',
        'conda_platforms': 'Platforms',
        'revision': 'Rev',
        'builds': 'Builds',
    }

    fmt = fmt_access if access else fmt_no_access
    if revisions:
        fmt = '%(revision)-6s | ' + fmt

    logger.info(fmt, package_header)


def format_package_type(value):
    value = str(value)
    try:
        return config.PackageType(value).label
    except ValueError:
        return value


def pprint_package(package, access=True, full_name=True, revision=False):
    package = package.copy()

    if package.get('published'):
        package['access'] = 'published'
    elif package['public']:
        package['access'] = 'public'
    else:
        package['access'] = 'private'

    if package.get('conda_platforms'):
        package['conda_platforms'] = ', '.join(
            str(item)
            for item in package['conda_platforms']
            if item is not None
        )

    if not full_name:
        package['full_name'] = package['name']

    if package.get('package_types'):
        package['package_types'] = ', '.join(
            format_package_type(item)
            for item in package['package_types']
            if item is not None
        )

    if package.get('builds'):
        package['builds'] = ', '.join(
            str(item)
            for item in package['builds']
            if item is not None
        )
    else:
        package['builds'] = ''

    fmt = fmt_access if access else fmt_no_access
    if revision:
        fmt = '%(revision)-6s | ' + fmt

    logger.info(fmt, package)
    if package.get('summary'):
        logger.info(' ' * 34 + '        : %s', package.get('summary'))  # pylint: disable=logging-not-lazy


def pprint_packages(packages, access=True, full_name=True, revisions=False):
    if packages:
        logger.info('Packages:')
    else:
        logger.info('No packages found')

    fmt = fmt_access if access else fmt_no_access
    if revisions:
        fmt = '%(revision)-6s | ' + fmt
    pprint_package_header(access, revisions=revisions)

    package_header = {
        'full_name': '-' * 32,
        'access': '-' * 12,
        'latest_version': '-' * 6,
        'conda_platforms': '-' * 15,
        'package_types': '-' * 17,
        'revision': '-' * 6,
        'builds': '-' * 10
    }

    logger.info(fmt, package_header)

    for package in sorted(packages, key=lambda pkg: pkg['full_name'] if full_name else pkg['name']):
        pprint_package(package, access, full_name, revision=revisions)


def pprint_user(user):
    user = user.copy()
    logger.info('Username: %s', user.pop('login'))
    logger.info('Member since: %s', parse_date(user.pop('created_at')).ctime())

    for key, value in user.items():
        logger.info('  +%s: %s', key, value)


def pprint_collections(collections):
    if collections:
        logger.info('Collections:')
    for collection in collections:
        collection['permission'] = 'public' if collection['public'] else 'private'
        logger.info('   + %(name)25s: [%(permission)s] %(description)s', collection)
