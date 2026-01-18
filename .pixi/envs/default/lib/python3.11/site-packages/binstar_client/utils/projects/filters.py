# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import fnmatch
import logging

from os.path import exists, isfile, join

logger = logging.getLogger('binstar.projects.upload')


class NoIgnoreFileException(IOError):
    def __init__(self, msg, *args, **kwargs):
        self.msg = msg
        super().__init__(msg, *args, **kwargs)


class FilterBase:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError

    def can_filter(self):
        return True

    def run(self, pfile):
        raise NotImplementedError


class VCSFilter(FilterBase):  # pylint: disable=abstract-method
    """Version Control System Filtering."""

    def __init__(self, pfiles, *args, **kwargs):  # pylint: disable=super-init-not-called
        self.pfiles = pfiles

    def run(self, pfile):
        if pfile.relativepath.startswith('.git/'):
            return False
        if pfile.relativepath.startswith('.svn/'):
            return False
        if pfile.relativepath.startswith('.hg/'):
            return False
        if pfile.relativepath.startswith('.anaconda/'):
            return False
        return True


class FilesFilter(FilterBase):  # pylint: disable=abstract-method
    """Ignore specific files."""

    ignored = ['.anaconda/project-local.yml', '.anaconda/project-local.yaml']

    def __init__(self, pfiles, *args, **kwargs):  # pylint: disable=super-init-not-called
        self.pfiles = pfiles

    def run(self, pfile):
        return pfile.relativepath not in self.ignored


class LargeFilesFilter(FilterBase):  # pylint: disable=abstract-method
    max_file_size = 2097152

    def __init__(self, pfiles, *args, **kwargs):  # pylint: disable=super-init-not-called
        self.pfiles = pfiles

    def run(self, pfile):
        if pfile.size > self.max_file_size:
            return False
        return True


class ProjectIgnoreFilter(FilterBase):  # pylint: disable=abstract-method
    def __init__(self, pfiles, *args, **kwargs):  # pylint: disable=super-init-not-called
        self._patterns = None
        self.pfiles = pfiles
        self.basepath = kwargs.get('basepath', '.')

    @property
    def patterns(self):
        if self._patterns is None:
            try:
                self._patterns = ignore_patterns(self.basepath)
            except NoIgnoreFileException:
                logger.debug('No ignore file')
        return self._patterns

    def can_filter(self):
        return self.patterns is not None and len(self.patterns) > 0

    def run(self, pfile):
        for pattern in self.patterns:
            if fnmatch.fnmatch(pfile.relativepath, pattern):
                return False
            if fnmatch.fnmatch(pfile.relativepath.split('/')[0], pattern):
                return False
        return True


def get_ignore_file(basepath):
    ignore_files = ['.projectignore', '.gitignore']
    for ignore_file in ignore_files:
        ignore_file_path = join(basepath, ignore_file)
        if exists(ignore_file_path) and isfile(ignore_file_path):
            logger.debug('Ignore patterns file: %s', ignore_file_path)
            return ignore_file_path
    raise NoIgnoreFileException('There is no .projectignore or .gitignore')


def ignore_patterns(basepath):
    patterns = []
    with open(get_ignore_file(basepath)) as ifile:  # pylint: disable=unspecified-encoding
        for row in ifile:
            pattern = remove_comments(clean(row))
            patterns.append(pattern)
    return patterns


def clean(cad):
    return cad.strip()


def remove_comments(cad):
    return cad.split('#', 1)[0].strip()


filters = [VCSFilter, ProjectIgnoreFilter, LargeFilesFilter]
