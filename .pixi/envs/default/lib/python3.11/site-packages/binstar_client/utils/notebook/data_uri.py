# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring

import base64
import io
import os
import sys
from urllib.parse import urlparse

import requests

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore

from ...errors import PillowNotInstalled

THUMB_SIZE = (340, 210)


class DataURIConverter:
    def __init__(self, location, data=None):
        self.check_pillow_installed()
        self.location = location
        self.data = data

    def check_pillow_installed(self):
        if Image is None:
            raise PillowNotInstalled()

    def __call__(self):
        if self.data:
            file = io.BytesIO(self.data)
            b64 = self._encode(self.resize_and_convert(file).read())
        elif os.path.exists(self.location):
            with open(self.location, 'rb') as file:
                b64 = self._encode(self.resize_and_convert(file).read())
        elif self.is_url():
            content = requests.get(self.location, timeout=10 * 60 * 60).content
            file = io.BytesIO()
            file.write(content)
            file.seek(0)
            b64 = self._encode(self.resize_and_convert(file).read())
        else:
            raise IOError('{} not found'.format(self.location))
        return b64

    def resize_and_convert(self, file):
        if Image is None:
            raise PillowNotInstalled()
        image = Image.open(file)
        image.thumbnail(THUMB_SIZE)
        out = io.BytesIO()
        image.save(out, format='png')
        out.seek(0)
        return out

    def is_py3(self):
        return sys.version_info[0] == 3

    def is_url(self):
        return self.location is not None and urlparse(self.location).scheme in ['http', 'https']

    def _encode(self, content):
        if self.is_py3():
            data64 = base64.b64encode(content).decode('ascii')
        else:
            data64 = content.encode('base64').replace('\n', '')
        return data64


def data_uri_from(location):
    return DataURIConverter(location)()


def data_uri_from_bytes(data):
    return DataURIConverter(location=None, data=data)()
