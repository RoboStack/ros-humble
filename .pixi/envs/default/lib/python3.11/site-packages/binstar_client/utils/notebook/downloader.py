# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import os
from collections import OrderedDict
from contextlib import suppress
from time import mktime

from dateutil.parser import parse

from binstar_client.errors import DestinationPathExists
from binstar_client.utils.config import PackageType


class Downloader:
    """
    Download files from your Anaconda repository.
    """

    def __init__(self, aserver_api, username, notebook):
        self.aserver_api = aserver_api
        self.username = username
        self.notebook = notebook
        self.output = None

    def __call__(self, package_types, output='.', force=False):
        self.output = output
        self.ensure_output()
        return self.download_files(package_types, force)

    def list_download_files(self, package_types, output='.', force=False):
        """
        This additional method was created to better handle the log output
        as files are downloaded one by one on the commands/download.py.
        """
        self.output = output
        self.ensure_output()
        files = OrderedDict()
        for file in self.list_files():
            pkg_type = file.get('type', '')
            with suppress(ValueError):
                pkg_type = PackageType(pkg_type)

            if pkg_type in package_types:
                if self.can_download(file, force):
                    files[file['basename']] = file
                else:
                    raise DestinationPathExists(file['basename'])
        return files

    def download_files(self, package_types, force=False):
        output = []
        for file in self.list_files():
            # Check type
            pkg_type = file.get('type', '')
            with suppress(ValueError):
                pkg_type = PackageType(pkg_type)

            if pkg_type in package_types:
                if self.can_download(file, force):
                    self.download(file)
                    output.append(file['basename'])
                else:
                    raise DestinationPathExists(file['basename'])
        return sorted(output)

    def download(self, dist):
        """
        Download file into location.
        """
        filename = dist['basename']
        requests_handle = self.aserver_api.download(
            self.username, self.notebook, dist['version'], filename
        )

        if not os.path.exists(os.path.dirname(filename)):
            try:
                os.makedirs(os.path.dirname(filename))
            except OSError:
                pass

        with open(os.path.join(self.output, filename), 'wb') as fdout:
            for chunk in requests_handle.iter_content(4096):
                fdout.write(chunk)

    def can_download(self, dist, force=False):
        """
        Can download if location/file does not exist or if force=True
        :param dist:
        :param force:
        :return: True/False
        """
        return not os.path.exists(os.path.join(self.output, dist['basename'])) or force

    def ensure_output(self):
        """
        Ensure output's directory exists
        """
        if not os.path.exists(self.output):
            os.makedirs(self.output)

    def list_files(self):
        """
        List available files in a project (aka notebook).
        :return: list
        """
        output = []
        tmp = {}

        files = self.aserver_api.package(self.username, self.notebook)['files']

        for file in files:
            if file['basename'] in tmp:
                tmp[file['basename']].append(file)
            else:
                tmp[file['basename']] = [file]

        for basename, versions in tmp.items():  # pylint: disable=unused-variable
            try:
                output.append(max(versions, key=lambda x: int(x['version'])))
            except ValueError:
                output.append(
                    max(versions, key=lambda x: mktime(parse(x['upload_time']).timetuple()))
                )
            except Exception:  # pylint: disable=broad-except
                output.append(versions[-1])

        return output
