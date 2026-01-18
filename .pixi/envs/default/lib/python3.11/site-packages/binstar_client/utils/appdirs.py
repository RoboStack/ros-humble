# -*- coding: utf-8 -*-

# pylint: disable=redefined-outer-name,import-outside-toplevel,line-too-long
# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

"""Utilities for determining application-specific dirs."""

import os.path


class EnvAppDirs:

    def __init__(self, root_path):
        self.root_path = root_path

    @property
    def user_data_dir(self):
        return os.path.join(self.root_path, 'data')

    @property
    def user_config_dir(self):
        return os.path.join(self.root_path, 'data')

    @property
    def site_data_dir(self):
        return os.path.join(self.root_path, 'data')

    @property
    def user_cache_dir(self):
        return os.path.join(self.root_path, 'cache')

    @property
    def user_log_dir(self):
        return os.path.join(self.root_path, 'log')
