# pylint: disable=missing-module-docstring,missing-function-docstring
from urllib.parse import urlparse

import nbformat

from ...errors import BinstarError


def parse(handle):
    """
    >>> parse("user/notebook")
    ('user', 'notebook')
    >>> parse("notebook")
    (None, 'notebook')

    :param handle: String
    :return: username, notebooks
    """

    components = handle.split('/', 1)
    if len(components) == 1:
        return None, components[0]
    if len(components) == 2:
        return components[0], components[1]
    raise BinstarError("{} can't be parsed".format(handle))


def notebook_url(upload_info):
    parsed = urlparse(upload_info['url'])
    if parsed.netloc == 'anaconda.org':
        url = '{}://notebooks.{}{}'.format(parsed.scheme, parsed.netloc, parsed.path)
    else:
        url = '{}://{}/notebooks{}'.format(parsed.scheme, parsed.netloc, parsed.path)
    return url


def has_environment(nb_file):
    if nbformat is None:
        return False

    try:
        with open(nb_file) as file:  # pylint: disable=unspecified-encoding
            data = file.read()
        notebook = nbformat.reader.reads(data)
        return 'environment' in notebook['metadata']
    except (ValueError, AttributeError, KeyError, IOError, nbformat.reader.NotJSONError):
        return False
