from typing import TYPE_CHECKING
from typing import Any
from typing import Optional

from requests.adapters import HTTPAdapter as BaseHttpAdapter

if TYPE_CHECKING:
    from ssl import SSLContext

    from urllib3 import PoolManager


class _SSLContextAdapterMixin:
    """Mixin to add the ``ssl_context`` constructor argument to HTTP adapters.

    The additional argument is forwarded directly to the pool manager. This allows us
    to dynamically decide what SSL store to use at runtime, which is used to implement
    the optional ``truststore`` backend.
    """

    def __init__(
        self,
        *,
        ssl_context: Optional["SSLContext"] = None,
        **kwargs: Any,
    ) -> None:
        self._ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(
        self,
        connections: int,
        maxsize: int,
        block: bool = False,
        **pool_kwargs: Any,
    ) -> "PoolManager":
        if self._ssl_context is not None:
            pool_kwargs.setdefault("ssl_context", self._ssl_context)
        return super().init_poolmanager(  # type: ignore[misc]
            connections=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs,
        )


class HTTPAdapter(_SSLContextAdapterMixin, BaseHttpAdapter):
    pass
