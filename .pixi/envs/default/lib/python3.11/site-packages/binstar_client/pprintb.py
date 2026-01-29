# pylint: disable=missing-module-docstring,missing-function-docstring

from pprint import pformat


def package_list(lst, verbose=True):
    if verbose:
        result = pformat(lst)
    else:
        result = '\n'.join('%-25s %s' % (pkg['full_name'], pkg['summary']) for pkg in lst)
    return result


def user_list(lst, verbose=True):
    if verbose:
        result = pformat(lst)
    else:
        result = '\n'.join('%-25s %s' % (user['login'], user['name']) for user in lst)
    return result
