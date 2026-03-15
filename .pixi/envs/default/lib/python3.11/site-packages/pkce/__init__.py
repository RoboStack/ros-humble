"""Simple module to generate PKCE code verifier and code challenge.

Examples
--------
>>> import pkce
>>> code_verifier, code_challenge = pkce.generate_pkce_pair()

>>> import pkce
>>> code_verifier = pkce.generate_code_verifier(length=128)
>>> code_challenge = pkce.get_code_challenge(code_verifier)
"""

import secrets
import hashlib
import base64
from typing import Tuple


def generate_code_verifier(length: int = 128) -> str:
    """Return a random PKCE-compliant code verifier.

    Parameters
    ----------
    length : int
        Code verifier length. Must verify `43 <= length <= 128`.

    Returns
    -------
    code_verifier : str
        Code verifier.

    Raises
    ------
    ValueError
        When `43 <= length <= 128` is not verified.
    """
    if not 43 <= length <= 128:
        msg = 'Parameter `length` must verify `43 <= length <= 128`.'
        raise ValueError(msg)
    code_verifier = secrets.token_urlsafe(96)[:length]
    return code_verifier


def generate_pkce_pair(code_verifier_length: int = 128) -> Tuple[str, str]:
    """Return random PKCE-compliant code verifier and code challenge.

    Parameters
    ----------
    code_verifier_length : int
        Code verifier length. Must verify
        `43 <= code_verifier_length <= 128`.

    Returns
    -------
    code_verifier : str
    code_challenge : str

    Raises
    ------
    ValueError
        When `43 <= code_verifier_length <= 128` is not verified.
    """
    if not 43 <= code_verifier_length <= 128:
        msg = 'Parameter `code_verifier_length` must verify '
        msg += '`43 <= code_verifier_length <= 128`.'
        raise ValueError(msg)
    code_verifier = generate_code_verifier(code_verifier_length)
    code_challenge = get_code_challenge(code_verifier)
    return code_verifier, code_challenge


def get_code_challenge(code_verifier: str) -> str:
    """Return the PKCE-compliant code challenge for a given verifier.

    Parameters
    ----------
    code_verifier : str
        Code verifier. Must verify `43 <= len(code_verifier) <= 128`.

    Returns
    -------
    code_challenge : str
        Code challenge that corresponds to the input code verifier.

    Raises
    ------
    ValueError
        When `43 <= len(code_verifier) <= 128` is not verified.
    """
    if not 43 <= len(code_verifier) <= 128:
        msg = 'Parameter `code_verifier` must verify '
        msg += '`43 <= len(code_verifier) <= 128`.'
        raise ValueError(msg)
    hashed = hashlib.sha256(code_verifier.encode('ascii')).digest()
    encoded = base64.urlsafe_b64encode(hashed)
    code_challenge = encoded.decode('ascii')[:-1]
    return code_challenge
