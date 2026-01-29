# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import inspect
import os
import tarfile
from tempfile import SpooledTemporaryFile
from binstar_client.errors import BinstarError


class CondaProject:
    # NOTE: This class will be moved into Anaconda-Project
    def __init__(self, project_path, *args, **kwargs):  # pylint: disable=unused-argument

        self.project_path = project_path
        self._name = None
        self._tar = None
        self._size = None
        self.pfiles = []
        self.metadata = {
            'summary': kwargs.get('summary', None),
            'description': kwargs.get('description', None),
            'version': kwargs.get('version', None)
        }
        self.metadata = {
            key: value
            for key, value in self.metadata.items()
            if value
        }

    def tar_it(self, file=SpooledTemporaryFile()):  # pylint: disable=consider-using-with
        with tarfile.open(mode='w', fileobj=file) as tar:
            for pfile in self.pfiles:
                tar.add(pfile.fullpath, arcname=pfile.relativepath)
        file.seek(0)
        self._tar = file
        return file

    def to_project_creation(self):
        return {
            'name': self.name,
            'access': 'public',
            'profile': {
                'description': self.metadata.get('description', ''),
                'summary': self.metadata.get('summary', ''),
            }
        }

    def to_stage(self):
        return {
            'basename': self.basename,
            'configuration': self.configuration,
        }

    @property
    def tar(self):
        if self._tar is None:
            self.tar_it()
        return self._tar

    @property
    def configuration(self):
        output = self.metadata.get('configuration', {})
        output.update({
            'size': self.size,
            'num_of_files': self.get_file_count()
        })
        return output

    def get_file_count(self):
        if os.path.isfile(self.project_path):
            return 1
        return len(self.pfiles)

    @property
    def basename(self):
        return f'{self.name}.tar'

    @property
    def size(self):
        if self._size is None:
            spos = self._tar.tell()
            self._tar.seek(0, os.SEEK_END)
            self._size = self._tar.tell() - spos
            self._tar.seek(spos)
        return self._size

    @property
    def name(self):
        if self._name is None:
            self._name = self._get_project_name()
        return self._name

    def _get_project_name(self):
        if os.path.isdir(self.project_path):
            return os.path.basename(os.path.abspath(self.project_path))
        return os.path.splitext(os.path.basename(self.project_path))[0]


class PFile:
    def __init__(self, **kwargs):
        self.fullpath = kwargs.get('fullpath', None)
        self.basename = kwargs.get('basename', None)
        self.relativepath = kwargs.get('relativepath', None)
        self.size = kwargs.get('size', None)
        self.populate()

    def __str__(self):
        if self.is_dir():
            return self.relativepath
        return f'[{self.size}] {self.relativepath}'

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.fullpath == other.fullpath

    def is_dir(self):
        return os.path.isdir(self.fullpath)

    def validate(self, validator):
        if inspect.isfunction(validator):
            return validator(basename=self.basename,
                             relativepath=self.relativepath,
                             fullpath=self.fullpath)

        if inspect.isclass(validator):
            return validator(self)()
        raise BinstarError(f'Invalid validator {validator}')

    def populate(self):
        if self.size is None:
            self.size = os.stat(self.fullpath).st_size
        if self.basename is None:
            self.basename = os.path.basename(self.fullpath)

    def to_dict(self):
        return {
            'basename': self.basename,
            'size': self.size,
            'relativepath': self.relativepath
        }
