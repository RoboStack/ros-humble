# pylint: disable=missing-module-docstring,missing-function-docstring

import os
import re
import time
from os.path import basename

from binstar_client import errors
from .data_uri import data_uri_from
from .inflection import parameterize

VALID_FORMATS = ['ipynb', 'csv', 'yml', 'yaml', 'json', 'md', 'rst', 'txt']


class Uploader:  # pylint: disable=too-many-instance-attributes
    """
    * Find or create a package (project)
    * Find or create release (version)
    * List files from project
    * Upload new files to project
    """
    _package = None
    _release = None
    _project = None

    def __init__(self, aserver_api, filepath, **kwargs):
        self.aserver_api = aserver_api
        self.filepath = filepath
        self._username = kwargs.get('user', None)
        self._version = kwargs.get('version', None)
        self._summary = kwargs.get('summary', None)
        self._thumbnail = kwargs.get('thumbnail', None)
        if 'name' in kwargs and kwargs['name'] is not None:
            self._project = parameterize(kwargs['name'])

    def upload(self, force=False):
        """
        Uploads a notebook
        :param force: True/False
        :returns {}
        """
        try:
            return self.aserver_api.upload(self.username, self.project, self.version,
                                           basename(self.filepath), open(self.filepath, 'rb'),
                                           self.filepath.split('.')[-1])
        except errors.Conflict as error:
            if force:
                self.remove()
                return self.upload()
            msg = 'Conflict: {} already exist in {}/{}'.format(self.filepath, self.project, self.version)
            raise errors.BinstarError(msg) from error

    def remove(self):
        return self.aserver_api.remove_dist(
            self, self.username, self.project, self.version, basename=self.notebook,  # pylint: disable=no-member
        )

    @property
    def notebook_attrs(self):
        if self._thumbnail is not None:
            return {'thumbnail': data_uri_from(self._thumbnail)}
        return {}

    @property
    def project(self):
        if self._project is None:
            return re.sub('\\-ipynb$', '', parameterize(os.path.basename(self.filepath)))
        return self._project

    @property
    def username(self):
        if self._username is None:
            self._username = self.aserver_api.user()['login']
        return self._username

    @property
    def version(self):
        if self._version is None:
            self._version = time.strftime('%Y.%m.%d.%H%M')
        return self._version

    @property
    def summary(self):
        if self._summary is None:
            self._summary = 'IPython notebook'
        return self._summary

    @property
    def package(self):
        if self._package is None:
            try:
                self._package = self.aserver_api.package(self.username, self.project)
            except errors.NotFound:
                self._package = self.aserver_api.add_package(self.username, self.project,
                                                             summary=self.summary,
                                                             attrs=self.notebook_attrs)
        return self._package

    @property
    def release(self):
        if self._release is None:
            try:
                self._release = self.aserver_api.release(self.username, self.project, self.version)
            except errors.NotFound:
                self._release = self.aserver_api.add_release(self.username, self.project,
                                                             self.version, None, None, None)
        return self._release

    @property
    def files(self):
        return self.package['files']
