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

import argparse
import os.path
import sys

from rosdistro import get_distribution
from rosdistro.freeze_source import CONCURRENT_DEFAULT, freeze_distribution_sources
from rosdistro.index import Index
from rosdistro.writer import yaml_from_distribution_file

import yaml


def parse_args(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='''
        Freeze a rosdistro\'s source branch versions to hashes or tags. If neither --release-version
        nor --release-tag are specified, the hashes of the current devel branches are used.
        ''')
    parser.add_argument('index', type=argparse.FileType(),
                        help='Path to a local index.yaml file.')
    parser.add_argument('dist_names', nargs='*', help='The names of the distributions (default: all)')
    parser.add_argument('-j', '--jobs', type=int, default=CONCURRENT_DEFAULT,
                        help='How many worker threads to use.')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress updating status bar (for script/CI usage).')

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--release-version', action='store_true',
                      help='Freeze to the hash of current release tag.')
    mode.add_argument('--release-tag', action='store_true',
                      help='Freeze to name of current release tag.')
    return parser.parse_args(args)


def main():
    args = parse_args()
    index = Index(
        yaml.safe_load(args.index),
        'file://%s' % os.path.dirname(os.path.abspath(args.index.name)))

    if not args.dist_names:
        args.dist_names = sorted(index.distributions.keys())

    for dist_name in args.dist_names:
        dist_url = index.distributions[dist_name]['distribution']
        if isinstance(dist_url, list):
            if len(dist_url) != 1:
                print('This script only works for distributions with a single distribution.yaml, '
                      'skipping distribution "%s"' % dist_name, file=sys.stderr)
                continue
            dist_url = dist_url[0]

        dist = get_distribution(index, dist_name)
        freeze_distribution_sources(
            dist, release_version=args.release_version, release_tag=args.release_tag,
            concurrent_ops=args.jobs, quiet=args.quiet)

        with open(dist_url.split('://')[1], 'w') as f:
            f.write(yaml_from_distribution_file(dist))


if __name__ == '__main__':
    sys.exit(main())
