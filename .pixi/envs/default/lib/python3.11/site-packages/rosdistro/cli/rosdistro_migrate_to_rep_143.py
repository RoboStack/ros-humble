import argparse
import sys

from rosdistro.verify import _yaml_header_lines

import yaml


def migrate(index_yaml):
    data = yaml.safe_load(open(index_yaml, 'r'))
    assert data['type'] == 'index'
    assert data['version'] == 2
    data['version'] = 3
    for distro_name in data['distributions']:
        distro_data = data['distributions'][distro_name]

        distro_data['distribution'] = [distro_data['distribution']]

        for key in ['doc_builds', 'release_builds', 'source_builds']:
            if key in distro_data:
                del distro_data[key]

    yaml_str = index_to_yaml(data)
    yaml_str = '\n'.join(_yaml_header_lines('index', data['version'])) + '\n' + yaml_str
    with open(index_yaml + '.new', 'w') as f:
        f.write(yaml_str)


def index_to_yaml(data):
    yaml_str = yaml.dump(data, default_flow_style=None)
    return yaml_str


def main():
    parser = argparse.ArgumentParser(description='Migrate the distros from REP 141 to REP 143.')
    parser.add_argument('index', help='The index.yaml file to migrate')
    args = parser.parse_args()

    migrate(args.index)


if __name__ == "__main__":
    sys.exit(main())
