# Software License Agreement (BSD License)
#
# Copyright (c) 2013, Open Source Robotics Foundation, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Open Source Robotics Foundation, Inc. nor
#    the names of its contributors may be used to endorse or promote
#    products derived from this software without specific prior
#    written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import gzip
import logging
import os
try:
    from cStringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
import yaml

logger = logging.getLogger('rosdistro')

from .distribution import Distribution  # noqa
from .distribution_cache import DistributionCache  # noqa
from .distribution_file import DistributionFile  # noqa
from .distribution_file import create_distribution_file  # noqa
from .external.appdirs import site_config_dir, user_config_dir  # noqa
from .index import Index  # noqa
from .loader import load_url  # noqa
from .manifest_provider.cache import CachedManifestProvider, CachedSourceManifestProvider  # noqa


# same version as in:
# - setup.py
# - stdeb.cfg
__version__ = '1.0.1'

# index information

DEFAULT_INDEX_URL = 'https://raw.githubusercontent.com/ros/rosdistro/master/index-v4.yaml'


def get_index_url():
    # environment variable has precedence over configuration files
    if 'ROSDISTRO_INDEX_URL' in os.environ:
        return os.environ['ROSDISTRO_INDEX_URL']

    def read_cfg_index_url(fname):
        try:
            with open(fname) as f:
                return yaml.safe_load(f.read())['index_url']
        except (IOError, KeyError, yaml.YAMLError):
            return None

    cfg_file = 'config.yaml'

    # first, look for the user configuration (usually ~/.config/rosdistro)
    user_cfg_path = os.path.join(user_config_dir('rosdistro'), cfg_file)
    index_url = read_cfg_index_url(user_cfg_path)
    if index_url is not None:
        return index_url

    # if not found, look for the global configuration *usually /etc/xdg/rosdistro)
    site_cfg_paths = os.path.join(site_config_dir('rosdistro', multipath=True), cfg_file).split(os.pathsep)
    for site_cfg_path in site_cfg_paths:
        index_url = read_cfg_index_url(site_cfg_path)
        if index_url is not None:
            return index_url

    # if nothing is found, use the default
    return DEFAULT_INDEX_URL


def get_index(url):
    logger.debug('Load index from "%s"' % url)
    yaml_str = load_url(url)
    data = yaml.safe_load(yaml_str)
    base_url = os.path.dirname(url)
    url_parts = urlparse(url)
    return Index(data, base_url, url_query=url_parts.query)


# distribution information

def get_distribution(index, dist_name):
    dist_file = get_distribution_file(index, dist_name)
    return Distribution(dist_file)


def get_distribution_file(index, dist_name):
    data = _get_dist_file_data(index, dist_name, 'distribution')
    return create_distribution_file(dist_name, data)


def get_distribution_files(index, dist_name):
    data = _get_dist_file_data(index, dist_name, 'distribution')
    if not isinstance(data, list):
        data = [data]
    dist_files = []
    for d in data:
        dist_file = DistributionFile(dist_name, d)
        dist_files.append(dist_file)
    return dist_files


def get_cached_distribution(index, dist_name, cache=None, allow_lazy_load=False):
    if cache is None:
        try:
            cache = get_distribution_cache(index, dist_name)
        except Exception:
            if not allow_lazy_load:
                raise
            # create empty cache instance
            dist_file_data = _get_dist_file_data(index, dist_name, 'distribution')
            cache = DistributionCache(dist_name, distribution_file_data=dist_file_data)
    dist = Distribution(
        cache.distribution_file,
        [CachedManifestProvider(cache, Distribution.default_manifest_providers if allow_lazy_load else None)],
        [CachedSourceManifestProvider(cache, Distribution.default_source_manifest_providers if allow_lazy_load else None)])
    assert cache.distribution_file.name == dist_name
    return dist


def get_distribution_cache_string(index, dist_name):
    if dist_name not in index.distributions.keys():
        raise RuntimeError("Unknown distribution: '{0}'. Valid distribution names are: {1}".format(dist_name, ', '.join(sorted(index.distributions.keys()))))
    dist = index.distributions[dist_name]
    if 'distribution_cache' not in dist.keys():
        raise RuntimeError("Distribution has no cache: '{0}'".format(dist_name))
    url = dist['distribution_cache']

    logger.debug('Load cache from "%s"' % url)
    if url.endswith('.yaml'):
        yaml_str = load_url(url)
    elif url.endswith('.yaml.gz'):
        yaml_gz_str = load_url(url, skip_decode=True)
        yaml_gz_stream = StringIO(yaml_gz_str)
        f = gzip.GzipFile(fileobj=yaml_gz_stream, mode='rb')
        yaml_str = f.read()
        f.close()
        if not isinstance(yaml_str, str):
            yaml_str = yaml_str.decode('utf-8')
    else:
        raise NotImplementedError('The url of the cache must end with either ".yaml" or ".yaml.gz"')
    return yaml_str


def get_distribution_cache(index, dist_name):
    yaml_str = get_distribution_cache_string(index, dist_name)
    data = yaml.safe_load(yaml_str)
    return DistributionCache(dist_name, data)


def get_package_condition_context(index, dist_name):
    if dist_name not in index.distributions.keys():
        raise RuntimeError("Unknown distribution: '{0}'. Valid distribution names are: {1}".format(dist_name, ', '.join(sorted(index.distributions.keys()))))

    condition_context = {
        'ROS_DISTRO': dist_name,
    }

    dist = index.distributions[dist_name]
    python_version = dist.get('python_version')
    if python_version:
        condition_context['ROS_PYTHON_VERSION'] = str(python_version)

    ros_version = {
        'ros1': '1',
        'ros2': '2',
    }.get(dist.get('distribution_type'))
    if ros_version:
        condition_context['ROS_VERSION'] = ros_version

    return condition_context


# internal

def _get_dist_file_data(index, dist_name, type_):
    if dist_name not in index.distributions.keys():
        raise RuntimeError("Unknown release: '{0}'. Valid release names are: {1}".format(dist_name, ', '.join(sorted(index.distributions.keys()))))
    dist = index.distributions[dist_name]
    if type_ not in dist.keys():
        raise RuntimeError('unknown release type "%s"' % type_)
    url = dist[type_]

    def _load_yaml_data(url):
        logger.debug('Load file from "%s"' % url)
        yaml_str = load_url(url)
        return yaml.safe_load(yaml_str)

    if not isinstance(url, list):
        data = _load_yaml_data(url)
    else:
        data = []
        for u in url:
            data.append(_load_yaml_data(u))
    return data


from .legacy import *  # noqa
