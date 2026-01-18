# -*- coding: utf8 -*-
# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

from __future__ import annotations

__all__ = ['upload_project']

import logging
import os
import shutil
import tempfile
import typing

from binstar_client import errors

if typing.TYPE_CHECKING:
    import argparse
    import types
    import anaconda_project.project
    import anaconda_project.internal.simple_status


logger = logging.getLogger('binstar.projects.upload')


class UploadedProject(typing.TypedDict):
    """Details on uploaded project."""

    username: str
    name: str
    url: str


class _TmpDir:

    def __init__(self, prefix: str = '') -> None:
        self._dir: str = tempfile.mkdtemp(prefix=prefix)

    def __enter__(self) -> str:
        return self._dir

    def __exit__(
            self,
            _type: typing.Optional[typing.Type[Exception]] = None,
            value: typing.Optional[Exception] = None,
            traceback: typing.Optional[types.TracebackType] = None,
    ) -> None:
        try:
            shutil.rmtree(path=self._dir)
        except Exception as error:  # pylint: disable=broad-except
            logger.debug('Failed to clean up TmpDir "%s": %s', self._dir, str(error))


def _real_upload_project(
        project: anaconda_project.project.Project,
        args: argparse.Namespace,
        username: str
) -> UploadedProject:
    try:
        # pylint: disable=import-outside-toplevel
        from anaconda_project import project_ops
    except ImportError as error:
        raise errors.BinstarError('anaconda-project package is not installed') from error

    logger.info('Uploading project: %s', project.name)
    status: anaconda_project.internal.simple_status.SimpleStatus = project_ops.upload(
        project,
        site=args.site,
        username=username,
        token=args.token,
        log_level=args.log_level,
    )
    if status:
        logger.info(status.status_description)
        return {
            'username': username,
            'name': project.name,
            'url': status.url,
        }

    status_error: typing.Any
    for status_error in status.errors:
        logger.error(str(status_error))
    logger.error(status.status_description)
    raise errors.BinstarError(status.status_description)


def upload_project(project_path: str, args: argparse.Namespace, username: str) -> UploadedProject:
    try:
        # pylint: disable=import-outside-toplevel
        from anaconda_project import project
        from anaconda_project import project_ops
    except ImportError as error:
        message: str = f'To upload projects such as "{project_path}", install the anaconda-project package.'
        logger.error(message)
        raise errors.BinstarError(message) from error

    if os.path.exists(project_path) and os.path.isdir(project_path):
        new_project = project.Project(directory_path=project_path)
        return _real_upload_project(new_project, args, username)

    # make the single file into a temporary project directory
    with (_TmpDir(prefix='anaconda_upload_')) as dirname:
        shutil.copy(project_path, dirname)
        basename_no_extension = os.path.splitext(os.path.basename(project_path))[0]
        new_project = project_ops.create(dirname, name=basename_no_extension)
        return _real_upload_project(new_project, args, username)
