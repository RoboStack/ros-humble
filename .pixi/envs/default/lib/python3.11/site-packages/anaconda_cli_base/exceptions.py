from collections import defaultdict
from typing import Callable, Dict, Type

from anaconda_cli_base.console import console

ErrorHandlingCallback = Callable[[Exception], int]


def catch_all(e: Exception) -> int:
    console.print(f"[bold][red]{e.__class__.__name__}:[/bold][/red] {e}")
    return 1


ERROR_HANDLERS: Dict[Type[Exception], ErrorHandlingCallback] = defaultdict(
    lambda: catch_all
)


def register_error_handler(exc: Type[Exception]) -> Callable:
    def decorator(f: ErrorHandlingCallback) -> Callable:
        ERROR_HANDLERS[exc] = f
        return f

    return decorator
