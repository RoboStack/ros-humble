import base64
import logging
from hashlib import blake2b
from socket import gethostname
from typing import Optional
from typing import Union

logger = logging.getLogger(__name__)


def get_hostname(hash: bool = False, pepper: Optional[str] = None) -> str:
    """
    Return the hostname for the current machine.

    Args:
        hash: Whether to hash the hostname.
        pepper: Optional pepper for additional security (base64 encoded)

    Returns:
        The hostname.
    """
    try:
        hostname = gethostname()
        if not hostname:
            logger.info("socket.gethostname returned an empty value")
    except Exception as e:
        logger.info(f"socket.gethostname raised an exception: {e}")
        hostname = ""

    if hostname.endswith(".local"):
        hostname = hostname.rsplit(".", 1)[0]
    if hash:
        hostname = hash_string("hostname", hostname, pepper)

    return hostname


def hash_string(what: str, s: str, pepper: Optional[Union[str, bytes]] = None) -> str:
    """
    Return the hashed string for the current machine.

    Args:
        what: The what to hash (example: "hostname").
        s: The string to hash.
        pepper: Optional pepper for additional security (base64 encoded)

    Returns:
        Hashed string
    """
    if isinstance(pepper, str):
        pepper = pepper.encode("utf-8")
    pepper = (pepper or b"")[: blake2b.SALT_SIZE]
    person = what.encode("utf-8")
    hfunc = blake2b(s.encode("utf-8"), digest_size=16, person=person, salt=pepper)  # type: ignore
    data = hfunc.digest()
    result = base64.urlsafe_b64encode(data).strip(b"=").decode("ascii")
    return result
