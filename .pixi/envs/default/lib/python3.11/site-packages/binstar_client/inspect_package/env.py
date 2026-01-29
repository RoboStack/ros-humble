# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import os
import time


from ..utils.yaml import yaml_load


class EnvInspector:
    def __init__(self, filename, fileobj):
        self._name = None
        self._version = None
        self.filename = filename
        self.content = yaml_load(fileobj)

    @property
    def basename(self):
        return os.path.basename(self.filename)

    @property
    def name(self):
        if self._name is None:
            self._name = self.content['name']
        return self._name

    def get_package_data(self):
        return {
            'name': self.name,
            'summary': 'Environment file'
        }

    @property
    def version(self):
        if self._version is None:
            self._version = time.strftime('%Y.%m.%d.%H%M%S')

        return self._version


def inspect_env_package(filename, fileobj, *args, **kwargs):  # pylint: disable=unused-argument
    environment = EnvInspector(filename, fileobj)

    package_data = environment.get_package_data()
    release_data = {
        'version': environment.version,
        'description': ''
    }
    file_data = {
        'basename': environment.basename,
        'attrs': {}
    }

    return package_data, release_data, file_data
