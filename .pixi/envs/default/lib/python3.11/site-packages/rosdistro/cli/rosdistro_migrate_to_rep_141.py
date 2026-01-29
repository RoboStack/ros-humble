import argparse
import gzip
import os
import sys

try:
    from cStringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO

from rosdistro.loader import load_url
from rosdistro.verify import _to_yaml, _yaml_header_lines

import yaml


def migrate(index_yaml):
    data = yaml.safe_load(open(index_yaml, 'r'))
    assert data['type'] == 'index'
    assert data['version'] == 1
    data['version'] = 2
    for distro_name in data['distributions']:
        distro_data = data['distributions'][distro_name]

        doc_file = distro_data['doc']
        release_file = distro_data['release']
        source_file = distro_data['source']
        del distro_data['doc']
        del distro_data['release']
        del distro_data['source']

        distribution_file = '%s/distribution.yaml' % distro_name
        distro_data['distribution'] = distribution_file

        generate_repos_file(index_yaml, distribution_file, doc_file, release_file, source_file)

        cache_url = distro_data['release_cache']
        del distro_data['release_cache']
        rel_cache_file = os.path.join(distro_name, '%s-cache.yaml' % distro_name)
        distro_data['distribution_cache'] = rel_cache_file + '.gz'

        base = os.path.dirname(index_yaml)
        cache_file = os.path.join(base, rel_cache_file)
        update_cache(index_yaml, distro_name, cache_url, cache_file, distribution_file)

    data = index_to_yaml(data)
    data = '\n'.join(_yaml_header_lines('index', data['version'])) + '\n' + data
    with open(index_yaml + '.new', 'w') as f:
        f.write(data)


def index_to_yaml(data):
    yaml_str = yaml.dump(data, default_flow_style=None)
    return yaml_str


def generate_repos_file(index_yaml, repos_file, doc_file, release_file, source_file):
    base = os.path.dirname(index_yaml)

    repos_url = os.path.join(base, repos_file)
    doc_url = os.path.join(base, doc_file)
    release_url = os.path.join(base, release_file)
    source_url = os.path.join(base, source_file)

    generate_repos_url(repos_url, doc_url, release_url, source_url)


def generate_repos_url(repos_url, doc_url, release_url, source_url):
    data = {}
    data['type'] = 'distribution'
    data['version'] = 1
    data['repositories'] = {}

    # migrate release stuff
    release_data = yaml.safe_load(open(release_url, 'r'))
    assert release_data['type'] == 'release'
    assert release_data['version'] == 1

    data['release_platforms'] = release_data['platforms']
    for repo_name in release_data['repositories']:
        repo_data = {}
        release_repo_data = release_data['repositories'][repo_name]

        repo_data['release'] = get_dict_parts(release_repo_data, ['tags', 'url', 'version'])
        if 'packages' in release_repo_data:
            pkgs = release_repo_data['packages']
            pkg_names = pkgs.keys()
            if len(pkg_names) > 1 or (len(pkg_names) == 1 and pkg_names[0] != repo_name):
                repo_data['release']['packages'] = sorted(pkg_names)
            for pkg_name in pkgs:
                if pkgs[pkg_name] is not None:
                    assert 'status' not in pkgs[pkg_name]
                    assert 'status_description' not in pkgs[pkg_name]

        repo_data.update(get_dict_parts(release_repo_data, ['status', 'status_description']))

        data['repositories'][repo_name] = repo_data

    # migrate doc stuff
    doc_data = yaml.safe_load(open(doc_url, 'r'))
    assert doc_data['type'] == 'doc'
    assert doc_data['version'] == 1

    for repo_name in doc_data['repositories']:
        doc_repo_data = doc_data['repositories'][repo_name]
        if repo_name not in data['repositories']:
            data['repositories'][repo_name] = {}
        data['repositories'][repo_name]['doc'] = get_dict_parts(doc_repo_data, ['type', 'url', 'version'])

    # migrate source stuff
    source_data = yaml.safe_load(open(source_url, 'r'))
    assert source_data['type'] == 'source'
    assert source_data['version'] == 1

    for repo_name in source_data['repositories']:
        source_repo_data = source_data['repositories'][repo_name]
        if repo_name not in data['repositories']:
            data['repositories'][repo_name] = {}
        data['repositories'][repo_name]['source'] = get_dict_parts(source_repo_data, ['type', 'url', 'version'])

    data = _to_yaml(data)
    data = '\n'.join(_yaml_header_lines('distribution', data['version'])) + '\n' + data
    with open(repos_url, 'w') as f:
        f.write(data)


def update_cache(index_yaml, distro_name, cache_url, cache_file, distribution_file):
    base = os.path.dirname(index_yaml)
    assert cache_url.endswith('.gz')
    yaml_gz_str = load_url(cache_url, skip_decode=True)
    yaml_gz_stream = StringIO(yaml_gz_str)
    f = gzip.GzipFile(fileobj=yaml_gz_stream, mode='rb')
    yaml_str = f.read()
    if not isinstance(yaml_str, str):
        yaml_str = yaml_str.decode('utf-8')
    f.close()
    cache_data = yaml.safe_load(yaml_str)

    del cache_data['release_file']
    distribution_data = yaml.safe_load(open(os.path.join(base, distribution_file), 'r'))
    cache_data['distribution_file'] = distribution_data

    cache_data['release_package_xmls'] = cache_data['package_xmls']
    del cache_data['package_xmls']

    cache_data['version'] = 2

    data = _to_yaml(cache_data)
    data = '\n'.join(_yaml_header_lines('cache', cache_data['version'])) + '\n' + data
    with open(cache_file, 'w') as f:
        f.write(data)

    with gzip.open(cache_file + '.gz', 'wb') as f:
        f.write(data)


def get_dict_parts(d, keys):
    data = {}
    for key in keys:
        if key in d:
            data[key] = d[key]
    return data


def main():
    parser = argparse.ArgumentParser(description='Migrate the distros from REP 137 to REP 141.')
    parser.add_argument('index', help='The index.yaml file to migrate')
    args = parser.parse_args()

    migrate(args.index)


if __name__ == "__main__":
    sys.exit(main())
