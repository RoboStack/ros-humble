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

import os
import tempfile

from contextlib import contextmanager

from catkin_pkg.package import InvalidPackage, parse_package_string
from catkin_pkg.packages import find_package_paths

from rosdistro.common import rmtree
from rosdistro.source_repository_cache import SourceRepositoryCache
from rosdistro.vcs import Git, ref_is_hash


def git_manifest_provider(_dist_name, repo, pkg_name):
    assert repo.version
    try:
        release_tag = repo.get_release_tag(pkg_name)
        with _temp_git_clone(repo.url, release_tag) as git_repo_path:
            filename = os.path.join(git_repo_path, 'package.xml')
            if not os.path.exists(filename):
                raise RuntimeError('Could not find package.xml in repository "%s"' % repo.url)
            with open(filename, 'r') as f:
                return f.read()
    except Exception as e:
        raise RuntimeError('Unable to fetch package.xml: %s' % e)


def git_source_manifest_provider(repo):
    try:
        with _temp_git_clone(repo.url, repo.version) as git_repo_path:
            # Include the git hash in our cache dictionary.
            git_hash = Git(git_repo_path).command('rev-parse', 'HEAD')['output']
            cache = SourceRepositoryCache.from_ref(git_hash)

            # Find package.xml files inside the repo.
            for package_path in find_package_paths(git_repo_path):
                if package_path == '.':
                    package_path = ''
                with open(os.path.join(git_repo_path, package_path, 'package.xml'), 'r') as f:
                    package_xml = f.read()
                try:
                    name = parse_package_string(package_xml).name
                except InvalidPackage:
                    raise RuntimeError('Unable to parse package.xml file found in %s' % repo.url)
                cache.add(name, package_path, package_xml)

    except Exception as e:
        raise RuntimeError('Unable to fetch source package.xml files: %s' % e)

    return cache


@contextmanager
def _temp_git_clone(url, ref):
    base = tempfile.mkdtemp('rosdistro')
    git = Git(cwd=base)
    try:
        if git.version_gte('1.8.0') and not ref_is_hash(ref):
            # Directly clone the required ref with least amount of additional history.
            # Available since git 1.8.0, but only works for tags and branches, not hashes:
            # https://git.kernel.org/cgit/git/git.git/tree/Documentation/git-clone.txt?h=v1.8.0#n158
            result = git.command('clone', url, '.', '--depth', '1', '--branch', ref)
            if result['returncode'] != 0:
                raise RuntimeError('Could not clone repository "%s" at reference "%s"' % (url, ref))
        else:
            # Old git doesn't support cloning a tag/branch directly, so full clone and checkout.
            result = git.command('clone', url, '.')
            if result['returncode'] != 0:
                raise RuntimeError('Could not clone repository "%s"' % url)

            result = git.command('checkout', ref)
            if result['returncode'] != 0:
                raise RuntimeError('Could not checkout ref "%s" of repository "%s"' % (ref, url))

        yield base
    finally:
        rmtree(base)
