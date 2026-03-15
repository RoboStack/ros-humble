# Software License Agreement (BSD License)
#
# Copyright (c) 2018, Open Source Robotics Foundation, Inc.
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


class SourceRepositoryCache(object):
    """
    This class represents a cache of the package XML strings for all packages in a single
    repo at a particular moment in time. A dictionary of many of these (one for each repo)
    keyed to the repo name represents the totality of the source package xml cache.
    """

    def __init__(self, data):
        assert data
        self._ref = data['_ref']
        self._package_names = set([name for name in data.keys() if name != '_ref'])
        self._data = data

    def get_data(self):
        """
        Return the bare data dict, suitable for serializing into yaml.
        """
        return self._data

    @classmethod
    def from_ref(cls, ref):
        """
        Create a new empty cache instance from just the version control reference hash.
        """
        return cls({'_ref': ref})

    def add(self, package_name, package_path, package_xml_string):
        """
        Add a package to the cache.
        """
        self._data[package_name] = (package_path, package_xml_string)
        self._package_names.add(package_name)

    def __iter__(self):
        """
        Iterate the list of package names in this cached repo. Returns an iterator of str.
        """
        return iter(self._package_names)

    def __getitem__(self, package_name):
        """
        Access the cached information about a specific package. Returns a (str, str) of
        path to package relative to repo root, and string of package xml.
        """ 
        if package_name not in self._package_names:
            raise KeyError("Package '%s' not present in SourceRepositoryCache." % package_name)
        return self._data[package_name]

    def items(self):
        """
        Generator of (str, str, str) containing the package name, path relative
        to repo root, and package xml string.
        """
        for package_name in self._package_names:
            package_path, package_xml_string = self._data[package_name]
            yield package_name, package_path, package_xml_string

    def __len__(self):
        """
        Returns the number of packages in this repo.
        """
        return len(self._package_names)

    def keys(self):
        """
        Return the list of packages in the repo cache.
        """
        return self._package_names

    def ref(self):
        """
        Return the version control hash.
        """
        return self._ref
