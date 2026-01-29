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

import subprocess
import sys
import threading
import time

try:
    import queue
except ImportError:
    import Queue as queue

CONCURRENT_DEFAULT = 16


def freeze_distribution_sources(dist, release_version=False, release_tag=False,
                                concurrent_ops=CONCURRENT_DEFAULT, quiet=False):
    # Populate this queue with tuples of repositories instances to be updated,
    # so that this work can be spread across multiple threads.
    work_queue = queue.Queue()
    for repo_name, repo in dist.repositories.items():
        # Only manipulate distribution entries with a source repo listed.
        if repo.source_repository:
            # Decide which git ref string we'll be using as the replacement match.
            if repo.release_repository and (release_version or release_tag):
                version = repo.release_repository.version.split('-')[0]
            else:
                version = repo.source_repository.version
            work_queue.put((repo.source_repository, version, release_tag))

    total_items = work_queue.qsize()

    for i in range(concurrent_ops):
        threading.Thread(target=_worker, args=[work_queue]).start()

    # Wait until the threads have done all the work and exited.
    while not work_queue.empty():
        time.sleep(0.1)
        if not quiet:
            sys.stdout.write("Updating source repo versions (%d/%d)   \r" %
                             (total_items - work_queue.qsize(), total_items))
            sys.stdout.flush()
    work_queue.join()

    # Clear past the updating line.
    if not quiet:
        print("")


# Get the repo commit information
def _get_repo_info(url, retry=2, retry_period=1):
    cmd = ['git', 'ls-remote', url]
    try:
        return subprocess.check_output(cmd).decode().splitlines()
    except subprocess.CalledProcessError as err:
        if not retry:
            raise
        print('  Non-zero return code for: %s, retrying in %f seconds' %
              (' '.join(cmd), retry_period), file=sys.stderr)
        # brief delay incase its an intermittent issue with infrastructure
        time.sleep(retry_period)
        return _get_repo_info(url, retry=retry - 1, retry_period=retry_period * 2)


def _worker(work_queue):
    while True:
        try:
            source_repo, freeze_version, freeze_to_tag = work_queue.get(block=False)
            ls_remote_lines = _get_repo_info(source_repo.url)
            for line in ls_remote_lines:
                hash, ref = line.split('\t', 1)
                if freeze_to_tag and ref == 'refs/tags/%s' % freeze_version:
                    source_repo.version = ref.split('refs/tags/')[1]
                    break
                elif ref in ('refs/heads/%s' % freeze_version, 'refs/tags/%s' % freeze_version):
                    source_repo.version = hash
                    break

            work_queue.task_done()

        except subprocess.CalledProcessError as e:
            print("No information could be retrieved for repo %s with error: %s" %
                  (source_repo.url, e), file=sys.stderr)
            work_queue.task_done()

        except queue.Empty:
            break
