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
import subprocess
import sys
import tempfile
from urllib.error import HTTPError

from rosdistro.common import rmtree
from rosdistro.loader import load_url
from rosdistro.release_file import ReleaseFile

import yaml


BASE_SRC_URL = 'https://raw.github.com/ros/rosdistro/master'


def get_targets():
    url = BASE_SRC_URL + '/releases/targets.yaml'
    print('Load "%s"' % url)
    yaml_str = load_url(url)
    data = yaml.safe_load(yaml_str)
    targets = {}
    for d in data:
        targets[d.keys()[0]] = d.values()[0]
    return targets


def convert_release(dist_name, targets):
    url = BASE_SRC_URL + '/releases/%s.yaml' % dist_name
    print('Load "%s"' % url)
    yaml_str = load_url(url)
    input_ = yaml.safe_load(yaml_str)

    # improve conversion performance by reusing results from last run
    last_dist = None
    if os.path.exists(dist_name + '/release.yaml'):
        with open(dist_name + '/release.yaml', 'r') as f:
            last_data = yaml.safe_load(f.read())
            last_dist = ReleaseFile(dist_name, last_data)

    output = {}
    output['type'] = 'release'
    output['version'] = 1
    output['platforms'] = {'ubuntu': targets[dist_name]}
    output['repositories'] = {}

    for repo_name in sorted(input_['repositories']):
        input_repo = input_['repositories'][repo_name]
        output_repo = {}
        output_repo['url'] = input_repo['url']
        output_repo['version'] = input_repo['version']
        if output_repo['version'] is None:
            print('- "' + repo_name + '" has no version')
            del output_repo['version']
        pkg_name = repo_name
        if 'packages' in input_repo:
            output_repo['packages'] = {}
            unary_repo = len(input_repo['packages']) == 1
            for pkg_name in input_repo['packages']:
                if unary_repo:
                    if input_repo['packages'][pkg_name] is None:
                        if pkg_name == repo_name:
                            del output_repo['packages']
                        else:
                            output_repo['packages'][pkg_name] = {'subfolder': pkg_name}
                    else:
                        output_repo['packages'][pkg_name] = input_repo['packages'][pkg_name]
                    break
                output_repo['packages'][pkg_name] = None
                if input_repo['packages'][pkg_name] is not None and input_repo['packages'][pkg_name] != pkg_name:
                    output_repo['packages'][pkg_name] = {'subfolder': input_repo['packages'][pkg_name]}
        output['repositories'][repo_name] = output_repo

        if 'version' in output_repo and output_repo['version'] is not None:
            tag_template = _get_tag_template(dist_name, output_repo, pkg_name, last_dist.repositories[repo_name] if last_dist and repo_name in last_dist.repositories else None)
            output_repo['tags'] = {'release': tag_template}

    yaml_str = yaml.dump(output, default_flow_style=False)
    yaml_str = yaml_str.replace(': null', ':')
    with open(dist_name + '/release.yaml', 'w') as f:
        f.write('%YAML 1.1\n')
        f.write('# ROS release file\n')
        f.write('# see REP 137: http://ros.org/reps/rep-0137.html\n')
        f.write('---\n')
        f.write(yaml_str)


def _get_tag_template(dist_name, repo, pkg_name, last_repo=None):
    # reuse tag template if fetched before for the same repo and version
    if last_repo and last_repo.version == repo['version']:
        if 'release' in last_repo.tags:
            return last_repo.tags['release']

    assert 'github.com' in repo['url']
    release_tag = 'release/{0}/{1}/{2}'.format(dist_name, pkg_name, repo['version'])
    url = _github_raw_url(repo['url'], release_tag)
    print('- ' + pkg_name + ': ' + url)
    try:
        try:
            load_url(url)
            return 'release/%s/{package}/{version}' % dist_name
        except HTTPError:
            # try alternative tag
            upstream_version = repo['version'].split('-')[0]
            release_tag = 'release/{0}/{1}'.format(pkg_name, upstream_version)
            url = _github_raw_url(repo['url'], release_tag)
            print('- ' + pkg_name + ': ' + url)
            load_url(url)
            return 'release/{package}/{upstream_version}'
    except HTTPError as e:
        raise RuntimeError('Could not determine tag using %s, %s, %s: %s' % (dist_name, repo, pkg_name, e))


def _github_raw_url(url, tag):
    url = url.replace('.git', '/tree/%s/' % tag)
    url = url.replace('git://', 'https://')
    # url = url.replace('https://', 'https://raw.')
    return url


def convert_source(dist_name):
    url = BASE_SRC_URL + '/releases/%s-devel.yaml' % dist_name
    print('Load "%s"' % url)
    yaml_str = load_url(url)
    input_ = yaml.safe_load(yaml_str)

    output = {}
    output['type'] = 'source'
    output['version'] = 1
    output['repositories'] = {}

    for repo_name in sorted(input_['repositories']):
        input_repo = input_['repositories'][repo_name]
        output_repo = {}
        output_repo['type'] = input_repo['type']
        output_repo['url'] = input_repo['url']
        output_repo['version'] = input_repo['version']
        if output_repo['type'] == 'svn' and output_repo['version'] is None:
            output_repo['version'] = 'HEAD'
        if output_repo['version'] is None:
            print('- "' + repo_name + '" has no version')
            del output_repo['version']
        output['repositories'][repo_name] = output_repo

    yaml_str = yaml.dump(output, default_flow_style=False)
    yaml_str = yaml_str.replace(': null', ':')
    with open(dist_name + '/source.yaml', 'w') as f:
        f.write('%YAML 1.1\n')
        f.write('# ROS source file\n')
        f.write('# see REP 137: http://ros.org/reps/rep-0137.html\n')
        f.write('---\n')
        f.write(yaml_str)


def convert_doc(dist_name):
    base = tempfile.mktemp()
    rc = subprocess.call(['git', 'clone', '--depth', '0', 'git://github.com/ros/rosdistro.git', base])
    if rc:
        print('Failed to checkout rosdistro repo', file=sys.stderr)
        rmtree(base)
        return

    doc_base = os.path.join(base, 'doc', dist_name)
    rosinstalls = {}
    rosinstall_depends = {}
    for filename in os.listdir(doc_base):
        if filename.endswith('.rosinstall'):
            name = os.path.splitext(os.path.basename(filename))[0]
            with open(os.path.join(doc_base, filename)) as f:
                data = yaml.safe_load(f)
            if name.endswith('_depends'):
                rosinstall_depends[name] = data
            else:
                rosinstalls[name] = data
    rmtree(base)
    # currently no doc has depends in groovy and hydro
    # assert not rosinstall_depends

    output = {}
    output['type'] = 'doc'
    output['version'] = 1
    output['repositories'] = {}

    for repo_name in sorted(rosinstalls.keys()):
        for input_repo in rosinstalls[repo_name]:
            output_repo = {}
            output_repo['type'] = input_repo.keys()[0]
            input_data = input_repo[output_repo['type']]
            output_repo['url'] = input_data['uri']
            if 'version' in input_data:
                output_repo['version'] = input_data['version']
            if output_repo['type'] == 'svn' and ('version' not in output_repo or output_repo['version'] is None):
                output_repo['version'] = 'HEAD'
            if 'version' not in output_repo or output_repo['version'] is None:
                print('- "' + repo_name + '" has no version')
                if 'version' in output_repo:
                    del output_repo['version']
            local_name = input_data['local-name']
            if local_name in output['repositories']:
                if output_repo == output['repositories'][local_name]:
                    print('- skip duplicate "%s"' % local_name)
                    continue
            key = local_name
            i = 1
            while key in output['repositories']:
                i += 1
                key = local_name + '_%d' % i
                print('- duplicate: %s %s -> %s' % (repo_name, local_name, key))
            if i > 1:
                # ignore duplicates
                print('  ignoring duplicate')
                continue
            output['repositories'][key] = output_repo

    yaml_str = yaml.dump(output, default_flow_style=False)
    yaml_str = yaml_str.replace(': null', ':')
    with open(dist_name + '/doc.yaml', 'w') as f:
        f.write('%YAML 1.1\n')
        f.write('# ROS doc file\n')
        f.write('# see REP 137: http://ros.org/reps/rep-0137.html\n')
        f.write('---\n')
        f.write(yaml_str)


def main():
    targets = get_targets()
    for distro in ['groovy', 'hydro']:
        print('\nConverting "%s"\n' % distro)
        convert_release(distro, targets)
        convert_source(distro)
        convert_doc(distro)


if __name__ == '__main__':
    sys.exit(main())
