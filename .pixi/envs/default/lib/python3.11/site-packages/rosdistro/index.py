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

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


class Index(object):

    _type = 'index'

    def __init__(self, data, base_url, url_query=''):
        assert 'type' in data, "Expected file type is '%s'" % Index._type
        assert data['type'] == Index._type, "Expected file type is '%s', not '%s'" % (Index._type, data['type'])

        assert 'version' in data, 'Index file lacks required version information'
        assert int(data['version']) > 1, "Unable to handle '%s' format version '%d' anymore, please update your '%s' file to version '2', '3', or '4'" % (Index._type, int(data['version']), Index._type)
        assert int(data['version']) in [2, 3, 4], "Unable to handle '%s' format version '%d', please update rosdistro (e.g. on Ubuntu/Debian use: sudo apt-get update && sudo apt-get install --only-upgrade python-rosdistro)" % (Index._type, int(data['version']))
        self.version = int(data['version'])

        self.distributions = {}
        if 'distributions' in data and data['distributions']:
            # if distributions is not a dict raise an exception including the value
            # this can be used to notify users (e.g. if an index.yaml file has been deleted / moved)
            if not isinstance(data['distributions'], dict):
                raise RuntimeError("Distributions type is invalid: expected 'dict', but got '%s': %s" % (type(data['distributions']).__name__, data['distributions']))
            for distro_name in sorted(data['distributions']):
                self.distributions[distro_name] = {}
                distro_data = data['distributions'][distro_name]
                for key in distro_data:
                    if key in ('distribution_status', 'distribution_type', 'python_version'):
                        assert self.version >= 4, "'%s' format version '%d' does not allow a '%s' entry" % (Index._type, self.version, key)
                        if key == 'python_version':
                            assert isinstance(distro_data[key], int), 'wrong type of key "%s"' % key
                        else:
                            assert isinstance(distro_data[key], str), 'wrong type of key "%s"' % key
                        self.distributions[distro_name][key] = distro_data[key]
                        continue

                    if key in ['distribution']:
                        if self.version == 2:
                            list_value = False
                        elif self.version in (3, 4):
                            list_value = True
                        else:
                            assert False
                    elif key in ['distribution_cache']:
                        list_value = False
                    elif key in ['release_builds', 'source_builds', 'doc_builds']:
                        if self.version == 2:
                            list_value = True
                        elif self.version in (3, 4):
                            assert False, "'%s' format version '%d' does not allow a '%s' entry anymore" % (Index._type, self.version, key)
                        else:
                            assert False
                    else:
                        if self.version <= 3:
                            assert False, 'unknown key "%s"' % key
                        # ignoring unknown keys
                        # in order to allow adding new ones in the future
                        # without the need to level the version
                        continue

                    self.distributions[distro_name][key] = []
                    value = distro_data[key]
                    if list_value != isinstance(value, list):
                        assert False, 'wrong type of key "%s"' % key

                    if not list_value:
                        value = [value]
                    for v in value:
                        parts = urlparse(v)
                        if not parts[0]:  # schema
                            v = base_url + '/' + v
                            if url_query:
                                v += '?' + url_query
                        self.distributions[distro_name][key].append(v)
                    if not list_value:
                        self.distributions[distro_name][key] = self.distributions[distro_name][key][0]

                    # for backward compatibility only
                    if key == 'distribution':
                        self.distributions[distro_name]['release'] = self.distributions[distro_name][key]

                # for backward compatibility only
                for key in ['release_builds', 'source_builds', 'doc_builds']:
                    if key not in self.distributions[distro_name]:
                        self.distributions[distro_name][key] = []
