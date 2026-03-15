from functools import cached_property

from panel.auth import OAuthLoginHandler
from panel.config import config

from anaconda_auth.config import AnacondaAuthConfig


class AnacondaLoginHandler(OAuthLoginHandler):
    """Anaconda OAuth2 Authentication

    To utilize this handler you must have a Client ID (key)
    and secret. The OAuth client at Anaconda must be configured for:

        * Set scopes: offline_access, openid, email, profile
        * Set redirect url to http://localhost:5006
        * Set grant type: Authorization Code
        * Set response types: ID Token, Token, Code
        * Set access token type: JWT
        * Set Authentication Method: HTTP Body

    """

    _access_token_header: str = "Bearer {}"

    _EXTRA_TOKEN_PARAMS: dict = {"grant_type": "authorization_code"}

    _USER_KEY: str = "email"
    _OAUTH_REDIRECT_URL: str = "http://localhost:5006"

    @cached_property
    def _config(self) -> AnacondaAuthConfig:
        return AnacondaAuthConfig()

    @property
    def _OAUTH_AUTHORIZE_URL(self) -> str:
        domain = config.oauth_extra_params.get("auth-domain", self._config.domain)  # type: ignore
        return f"https://{domain}/oauth2/auth"

    @property
    def _OAUTH_USER_URL(self) -> str:
        domain = config.oauth_extra_params.get("auth-domain", self._config.domain)  # type: ignore
        return f"https://{domain}/oauth2/userinfo"

    @property
    def _OAUTH_ACCESS_TOKEN_URL(self) -> str:
        domain = config.oauth_extra_params.get("auth-domain", self._config.domain)  # type: ignore
        return f"https://{domain}/oauth2/token"
