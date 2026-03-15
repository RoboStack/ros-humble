"""Defines an auth handler to inject an Authorization header into each request.

Tokens are assumed to be installed onto a user's system via a separate CLI command.

"""

from fnmatch import fnmatch
from functools import lru_cache
from typing import Any
from typing import NamedTuple
from typing import Optional
from typing import Protocol
from urllib.parse import ParseResult
from urllib.parse import urlparse

from conda import CondaError
from conda.base.context import Context
from conda.plugins.types import ChannelAuthBase
from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError
from requests import PreparedRequest
from requests import Response

from anaconda_auth._conda import repo_config
from anaconda_auth._conda.config import TOKEN_DOMAIN_MAP
from anaconda_auth._conda.config import CredentialType
from anaconda_auth.config import AnacondaAuthConfig
from anaconda_auth.exceptions import TokenNotFoundError
from anaconda_auth.token import TokenInfo

URI_PREFIX = "/repo/"


class ResponseHook(Protocol):
    # Type alias/protocol for requests response hook
    def __call__(self, response: Response, **_: Any) -> Response: ...


class AccessCredential(NamedTuple):
    """Represents a typed string containing an access credential (of CredentialType)."""

    # This is essentially a tagged union, which felt lightweight and appropriate for our needs
    value: Optional[str]
    type: CredentialType


class AnacondaAuthError(CondaError):
    """
    A generic error to raise that is a subclass of CondaError so we don't trigger the unhandled exception traceback.
    """


def _load_channel_settings(channel_name: str) -> dict[str, Any]:
    """Find the correct channel settings from conda's configuration."""
    # TODO(mattkram): Open conda issue to see if we can pass this into the AuthHandler
    #                 as part of the plugin protocol.

    # Since the conda logic uses a url, we derive a url from the channel name
    # this will not work for multi_channels like "defaults", but we restrict the
    # extra fields we need to URL-based channel_settings, which should be sufficient.
    url = channel_name
    if not url.endswith("/"):
        url += "/"

    parsed_url = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        return {}

    # The following implementation has mostly been copied from conda, with one noted exception.
    # Ideally, we can receive the settings in the plugin instantiation.
    # See: https://github.com/conda/conda/blob/2af8e0f7255e1d06ea0bfcb6076c7427d101feee/conda/gateways/connection/session.py#L91-L112

    # We ensure here if there are duplicates defined, we choose the last one
    channel_settings = {}
    context = Context()
    for settings in context.channel_settings:
        channel = settings.get("channel", "")
        if channel == channel_name:
            # First we check for exact match
            channel_settings = settings
            continue

        parsed_setting = urlparse(channel)

        # We require that the schemes must be identical to prevent downgrade attacks.
        # This includes the case of a scheme-less pattern like "*", which is not allowed.
        if parsed_setting.scheme != parsed_url.scheme:
            continue

        url_without_schema = parsed_url.netloc + parsed_url.path
        pattern = parsed_setting.netloc + parsed_setting.path
        if fnmatch(url_without_schema, pattern):
            channel_settings = settings

    return channel_settings


class AnacondaAuthHandlerExtraSettings(BaseModel):
    override_auth_domain: Optional[str] = Field(default=None, alias="auth_domain")
    override_credential_type: Optional[CredentialType] = Field(
        default=None, alias="credential_type"
    )

    @classmethod
    def from_channel_name(cls, channel_name: str) -> "AnacondaAuthHandlerExtraSettings":
        """Load extra settings for a channel, with validation."""
        settings = _load_channel_settings(channel_name)
        try:
            return cls(**settings)
        except ValidationError as e:
            raise AnacondaAuthError(
                f"""Error when loading anaconda-auth extra configuration from your condarc.\n\n{e}"""
            )


class AnacondaAuthHandler(ChannelAuthBase):
    def __init__(self, channel_name: str, *args: Any, **kwargs: Any):
        super().__init__(channel_name, *args, **kwargs)
        self._extras = AnacondaAuthHandlerExtraSettings.from_channel_name(channel_name)

    def _load_token_domain(self, parsed_url: ParseResult) -> tuple[str, CredentialType]:
        """Select the appropriate domain for token lookup based on a parsed URL.

        We also determine whether to use API key or legacy repo token. This method
        handles a default set of rules, as well as user overrides via conda
        channel_settings.

        """
        channel_domain = parsed_url.netloc.lower()

        # Set defaults for behavior when not overridden by configuration
        token_domain = channel_domain
        credential_type = CredentialType.API_KEY

        # For specific channel domains, we override the defaults
        if channel_domain in TOKEN_DOMAIN_MAP:
            token_domain, credential_type, _ = TOKEN_DOMAIN_MAP[channel_domain]

        # Allow users to override default via configuration
        config = AnacondaAuthConfig(domain=token_domain)
        if config.use_unified_repo_api_key:
            credential_type = CredentialType.API_KEY

        if self._extras.override_auth_domain:
            token_domain = self._extras.override_auth_domain

        if self._extras.override_credential_type:
            credential_type = self._extras.override_credential_type

        return token_domain, credential_type

    def _load_token_from_keyring(
        self,
        token_domain: str,
        credential_type: CredentialType,
        parsed_url: ParseResult,
    ) -> Optional[AccessCredential]:
        """Attempt to load an appropriate token from the keyring.

        We parse the requested URL, extract what may be an organization ID, and first
        attempt to load the token for that specific organization. If that fails, we
        then simply return the first token in the keyring (since this is in all likelihood
        one of the default channels ('main', 'r', etc.).

        If no token can be found in the keyring, we return None, which means that
        the token will attempt to be read from via conda-token instead.

        """
        try:
            token_info = TokenInfo.load(token_domain)
        except TokenNotFoundError:
            # Fallback to conda-token if the token is not found in the keyring
            return None

        # Load the API key directly from the keyring
        if token_info.api_key and credential_type == CredentialType.API_KEY:
            return AccessCredential(token_info.api_key, CredentialType.API_KEY)

        # If we are looking for a repo token, we first attempt to parse the URL
        # and extract the org slug (for repo.anaconda.cloud)
        path = parsed_url.path
        if path.startswith(URI_PREFIX):
            path = path[len(URI_PREFIX) :]
        maybe_org, _, _ = path.partition("/")

        # First we attempt to return an organization-specific token
        try:
            return AccessCredential(
                token_info.get_repo_token(maybe_org), CredentialType.REPO_TOKEN
            )
        except TokenNotFoundError:
            pass

        # Return the first one, assuming this is not an org-specific channel
        try:
            return AccessCredential(
                token_info.repo_tokens[0].token, CredentialType.REPO_TOKEN
            )
        except IndexError:
            pass

        return None

    @staticmethod
    def _load_token_via_conda_token(
        parsed_url: ParseResult,
    ) -> Optional[AccessCredential]:
        domain = parsed_url.netloc.lower()
        # Try to load the token via conda-token if that is installed
        if repo_config is not None:
            tokens = repo_config.token_list()
            for token_url, token in tokens.items():
                token_netloc = urlparse(token_url).netloc
                if token_netloc.lower() == domain and token is not None:
                    return AccessCredential(token, CredentialType.REPO_TOKEN)
        return None

    @lru_cache
    def _load_token(self, url: str) -> AccessCredential:
        """Load the appropriate token based on URL matching.

        First, attempts to load from the keyring. If that fails, we attempt
        to load the legacy repo token via conda-token.

        Cached for performance.

        Args:
            url: The URL for the request.

        Returns:
             The token, if it can be loaded. None, otherwise.

        """
        parsed_url = urlparse(url)
        token_domain, credential_type = self._load_token_domain(parsed_url)

        # First, we try to load the token from the keyring. If it is not found, we fall through
        if token := self._load_token_from_keyring(
            token_domain, credential_type, parsed_url
        ):
            return token
        elif token := self._load_token_via_conda_token(parsed_url):
            return token
        return AccessCredential(None, credential_type)

    @lru_cache
    def _build_header(self, url: str) -> tuple[Optional[str], CredentialType]:
        """Build the Authorization header based on the request URL.

        The result can vary in terms of "token" vs. "Bearer" as well as whether the
        credential is a legacy repo token or an API key.

        """
        try:
            token = self._load_token(url)
            if token.value is None:
                return None, token.type

            if token.type == CredentialType.REPO_TOKEN:
                return f"token {token.value}", token.type

            return f"Bearer {token.value}", token.type
        except Exception:
            # TODO(mattkram): We need to be very resilient about exceptions here for now
            return None, token.type

    def _build_response_handler(
        self,
        credential_type: CredentialType,
    ) -> ResponseHook:
        instruction = (
            "anaconda token install"
            if credential_type == CredentialType.REPO_TOKEN
            else "anaconda login"
        )

        def handler(response: Response, **_: Any) -> Response:
            """Raise a nice error message if the authentication token is missing."""
            if response.status_code in {401, 403}:
                if response.request.headers.get("Authorization") is not None:
                    message = (
                        f"Received authentication error ({response.status_code}) when accessing {self.channel_name}. "
                        f"If your token is invalid or expired, please re-install with `{instruction}`."
                    )
                else:
                    message = (
                        f"Token not found for {self.channel_name}. "
                        f"Please install token with `{instruction}`."
                    )
                raise AnacondaAuthError(message)
            return response

        return handler

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Inject the token as an Authorization header on each request."""

        # Technically the request URL may not be set yet
        if request.url is None:
            return request

        # Build the authorization header if there is a credential stored, and
        # determine the credential type expected for the channel
        header, credential_type = self._build_header(request.url)

        # Register a hook to handle error responses
        request.register_hook(
            "response",
            self._build_response_handler(credential_type),
        )

        if header:
            request.headers["Authorization"] = header

        return request
