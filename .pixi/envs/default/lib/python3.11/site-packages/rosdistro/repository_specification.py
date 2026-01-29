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

import re

from .vcs import Git


class RepositorySpecification(object):
    # Match groups are server and path on server.
    VCS_REGEX = re.compile(r'(?:https?:\/\/|ssh:\/\/|git:\/\/|git@)((?:[a-fA-F0-9]{40}@)?[\w.-]+)[:/]([\w/-]*)(?:\.git)?$')

    def __init__(self, name, data):
        self.name = name
        self.type = data.get('type', 'git')
        assert 'url' in data and data['url'], "Repository '%s' lacks required URL information" % name
        self.url = data['url']
        self.version = data.get('version', None)
        self._remote_refs = None

        # for backward compatibility only
        self.status = None
        self.status_description = None

    def get_data(self):
        return self._get_data()

    def get_url_parts(self):
        """ Returns a tuple for the server and path, eg ('github.com', 'ros/catkin') """
        match = self.VCS_REGEX.match(self.url)
        if not match:
            raise RuntimeError('VCS url "%s" does not match expected format.' % self.url)
        return match.groups()

    def has_remote_tag(self, tag):
        return tag in self.remote_tags

    @property
    def remote_refs(self):
        if not self._remote_refs:
            result = Git().command('ls-remote', self.url)
            if result['returncode'] != 0:
                raise RuntimeError('Could not git ls-remote repository "%s"' % self.url)
            self._remote_refs = {}
            for row in result['output'].strip().splitlines():
                sha, name = row.split('\t')
                self._remote_refs[name] = sha
        return self._remote_refs

    @property
    def remote_tags(self):
        result = {}
        for name, sha in self.remote_refs.items():
            if name.startswith('refs/tags/'):
                result[name.split('refs/tags/')[1]] = sha
        return result

    def _get_data(self, skip_git_type=False):
        data = {}
        if self.type != 'git' or not skip_git_type:
            data['type'] = str(self.type)
        data['url'] = str(self.url)
        if self.version is not None:
            data['version'] = self.version
        return data
