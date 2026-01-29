# -*- coding: utf8 -*-

"""Utilities to configure logging for the application."""

from __future__ import annotations

__all__ = ['setup_logging']

import logging.handlers
import os
import sys
import types
import typing

import urllib3.exceptions

from . import config


def _custom_excepthook(
        logger: logging.Logger,
        show_traceback: bool = False,
) -> typing.Callable[[typing.Type[BaseException], BaseException, typing.Optional[types.TracebackType]], None]:
    """Generate custom exception hook to log captured exceptions."""
    def excepthook(
            exc_type: typing.Type[BaseException],
            exc_value: BaseException,
            exc_traceback: typing.Optional[types.TracebackType],
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            return
        if show_traceback:
            logger.error('', exc_info=(exc_type, exc_value, exc_traceback))
        else:
            logger.error('%s', exc_value)

    return excepthook


class ConsoleFormatter(logging.Formatter):
    """Custom logging formatter."""

    FORMAT_DEFAULT: typing.Final[str] = '[%(levelname)s] %(message)s'
    FORMAT_CUSTOM: typing.Final[typing.Mapping[int, str]] = {logging.INFO: '%(message)s'}

    def format(self, record: logging.LogRecord) -> str:
        """Format log record before printing it."""
        # pylint: disable=protected-access
        self._style._fmt = self.FORMAT_CUSTOM.get(record.levelno, self.FORMAT_DEFAULT)
        return super().format(record)


def setup_logging(
        logger: logging.Logger,
        log_level: int = logging.INFO,
        show_traceback: bool = False,
        disable_ssl_warnings: bool = False
) -> None:
    """Configure logging for the application."""
    logger.setLevel(logging.DEBUG)

    os.makedirs(config.USER_LOGDIR, exist_ok=True)
    log_file: str = os.path.join(config.USER_LOGDIR, 'cli.log')

    file_handler: logging.Handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * (1024 ** 2),
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(name)-15s %(message)s'))
    logger.addHandler(file_handler)

    console_handler: logging.Handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)

    sys.excepthook = _custom_excepthook(logger, show_traceback=show_traceback)

    if disable_ssl_warnings:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
