# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import json
import os
import traceback


class JSONFormatter:  # pylint: disable=too-few-public-methods

    def __init__(self, *args, **extra_tags):
        self.dumps = extra_tags.pop('dumps', lambda obj: json.dumps(obj, default=str))

        object.__init__(self, *args)
        self.extra_tags = extra_tags

    def format(self, record):

        if isinstance(record.msg, dict):
            data = record.msg
        elif isinstance(record.msg, (list, tuple)):
            data = {'items': record.msg}
        else:
            data = {'msg': record.msg}

        kwargs = self.extra_tags.copy()

        data.update(logLevel=record.levelname,
                    logModule=record.module,
                    logName=record.name,
                    pid=os.getpid(),
                    **kwargs)

        if record.exc_info:
            etype, value, trace = record.exc_info
            trace = '\n'.join(traceback.format_exception(etype, value, trace))
            data['exception'] = True
            data['traceback'] = trace

        msg = self.dumps(data)
        return msg
