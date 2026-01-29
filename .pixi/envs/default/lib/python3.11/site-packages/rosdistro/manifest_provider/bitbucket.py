# Software License Agreement (BSD License)
#
# Copyright (c) 2016, Clearpath Robotics
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

import base64
import os
from urllib.request import urlopen, Request
from urllib.error import URLError

from rosdistro import logger

# This Bitbucket provider can optionally send basic auth to fetch from
# private repositories if you supply the environment variables
# BITBUCKET_USER and BITBUCKET_PASSWORD. This can be the credentials
# for an actual Bitbucket user, or it can be a team name with API key.
#
# Generate an API key for your team here:
# https://bitbucket.org/account/user/<team-name>/api-key/
BITBUCKET_USER = os.getenv('BITBUCKET_USER', None)
BITBUCKET_PASSWORD = os.getenv('BITBUCKET_PASSWORD', None)


def bitbucket_manifest_provider(_dist_name, repo, pkg_name):
    assert repo.version
    server, path = repo.get_url_parts()

    if not server.endswith('bitbucket.org'):
        logger.debug('Skip non-bitbucket url "%s"' % repo.url)
        raise RuntimeError('Cannot handle non bitbucket url.')

    release_tag = repo.get_release_tag(pkg_name)

    if not repo.has_remote_tag(release_tag):
        raise RuntimeError('specified tag "%s" is not a git tag' % release_tag)

    url = 'https://bitbucket.org/%s/raw/%s/package.xml' % (path, release_tag)
    try:
        logger.debug('Load package.xml file from url "%s"' % url)
        req = Request(url)
        if BITBUCKET_USER and BITBUCKET_PASSWORD:
            logger.debug('- using http basic auth from supplied environment variables.')
            credential_pair = '%s:%s' % (BITBUCKET_USER, BITBUCKET_PASSWORD)
            authheader = 'Basic %s' % base64.b64encode(credential_pair.encode()).decode()
            req.add_header('Authorization', authheader)
        package_xml = urlopen(req).read().decode('utf-8')
        return package_xml
    except URLError as e:
        logger.debug('- failed (%s)' % e)
        raise RuntimeError()
