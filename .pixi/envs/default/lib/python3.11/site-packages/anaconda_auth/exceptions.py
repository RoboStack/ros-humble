class AuthenticationError(Exception):
    pass


class InvalidTokenError(AuthenticationError):
    pass


class TokenNotFoundError(Exception):
    pass


class LoginRequiredError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


class UnknownSiteName(Exception):
    pass


class DeviceFlowError(Exception):
    """Base exception for device flow errors."""

    pass


class DeviceFlowTimeout(DeviceFlowError):
    """Device authorization timed out."""

    pass


class DeviceFlowDenied(DeviceFlowError):
    """User denied device authorization."""

    pass
