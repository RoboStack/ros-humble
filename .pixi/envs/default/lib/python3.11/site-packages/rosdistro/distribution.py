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

from .manifest_provider.bitbucket import bitbucket_manifest_provider
from .manifest_provider.git import git_manifest_provider, git_source_manifest_provider
from .manifest_provider.github import github_manifest_provider, github_source_manifest_provider
from .manifest_provider.tar import tar_manifest_provider, tar_source_manifest_provider
from .package import Package


class Distribution(object):

    default_manifest_providers = [github_manifest_provider, bitbucket_manifest_provider, git_manifest_provider, tar_manifest_provider]
    default_source_manifest_providers = [github_source_manifest_provider, git_source_manifest_provider, tar_source_manifest_provider]

    def __init__(self, distribution_file, manifest_providers=None, source_manifest_providers=None):
        self._distribution_file = distribution_file

        # Use default
        self._manifest_providers = Distribution.default_manifest_providers
        self._source_manifest_providers = Distribution.default_source_manifest_providers

        # Override default if given
        if manifest_providers is not None:
            self._manifest_providers = manifest_providers
        if source_manifest_providers is not None:
            self._source_manifest_providers = source_manifest_providers

        self._release_package_xmls = {}
        self._source_repo_package_xmls = {}

    def __getattr__(self, name):
        return getattr(self._distribution_file, name)

    def get_release_package_xml(self, pkg_name):
        if pkg_name not in self._release_package_xmls:
            pkg = self._distribution_file.release_packages[pkg_name]
            repo_name = pkg.repository_name
            repo = self._distribution_file.repositories[repo_name]
            if repo.release_repository is None:
                return None
            repo = repo.release_repository
            if repo.version is None:
                return None
            package_xml = None
            for mp in self._manifest_providers:
                package_xml = mp(self._distribution_file.name, repo, pkg_name)
                if package_xml is not None:
                    break
            self._release_package_xmls[pkg_name] = package_xml
        return self._release_package_xmls[pkg_name]

    def get_source_package_xml(self, pkg_name):
        repo_name = self._distribution_file.source_packages[pkg_name].repository_name
        repo_cache = self.get_source_repo_package_xmls(repo_name)
        if repo_cache:
            return repo_cache[pkg_name][1]
        else:
            return None

    def get_source_repo_package_xmls(self, repo_name):
        if repo_name in self._source_repo_package_xmls:
            return self._source_repo_package_xmls[repo_name]
        else:
            for mp in self._source_manifest_providers:
                repo_cache = mp(self.repositories[repo_name].source_repository)
                if repo_cache is not None:
                    # Update map of package XMLs, and also list of known package names.
                    self._source_repo_package_xmls[repo_name] = repo_cache
                    for pkg_name in repo_cache:
                        if pkg_name[0] != '_':
                            self._distribution_file.source_packages[pkg_name] = Package(pkg_name, repo_name)
                    return self._source_repo_package_xmls[repo_name]
        return None
