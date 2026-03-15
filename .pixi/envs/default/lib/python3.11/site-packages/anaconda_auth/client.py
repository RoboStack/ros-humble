import json
import warnings
from functools import cached_property
from hashlib import md5
from typing import Any
from typing import Dict
from typing import MutableMapping
from typing import Optional
from typing import Union
from typing import cast
from urllib.parse import urljoin

import requests
from requests import PreparedRequest
from requests import Response
from requests.auth import AuthBase

from anaconda_auth import __version__ as version
from anaconda_auth.adapters import HTTPAdapter
from anaconda_auth.config import AnacondaAuthConfig
from anaconda_auth.config import AnacondaAuthSite
from anaconda_auth.exceptions import TokenExpiredError
from anaconda_auth.exceptions import TokenNotFoundError
from anaconda_auth.token import TokenInfo
from anaconda_auth.utils import get_hostname
from anaconda_cli_base.exceptions import AnacondaConfigValidationError

# VersionInfo was renamed and is deprecated in semver>=3
try:
    from semver.version import Version
except ImportError:
    # In semver<3, it's called VersionInfo
    from semver import VersionInfo as Version


def login_required(response: Response, *args: Any, **kwargs: Any) -> Response:
    has_auth_header = response.request.headers.get("Authorization", False)

    if response.status_code in [401, 403]:
        try:
            error_code = response.json().get("error", {}).get("code", "")
        except requests.JSONDecodeError:
            error_code = ""

        if error_code == "auth_required":
            if has_auth_header:
                response.reason = "Your API key or login token is invalid."
            else:
                response.reason = (
                    "You must login before using this API endpoint"
                    " or provide an api_key to your client."
                )

    return response


class BearerAuth(AuthBase):
    def __init__(
        self, domain: Optional[str] = None, api_key: Optional[str] = None
    ) -> None:
        self.api_key = api_key
        if domain is None:
            domain = AnacondaAuthConfig().domain

        self._token_info = TokenInfo(domain=domain)

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        if not self.api_key:
            try:
                r.headers["Authorization"] = (
                    f"Bearer {self._token_info.get_access_token()}"
                )
            except (TokenNotFoundError, TokenExpiredError):
                pass
        else:
            r.headers["Authorization"] = f"Bearer {self.api_key}"
        return r


class BaseClient(requests.Session):
    _user_agent: str = f"anaconda-auth/{version}"
    _api_version: Optional[str] = None

    def __init__(
        self,
        site: Optional[Union[str, AnacondaAuthSite]] = None,
        base_uri: Optional[str] = None,
        domain: Optional[str] = None,
        auth_domain_override: Optional[str] = None,
        api_key: Optional[str] = None,
        user_agent: Optional[str] = None,
        api_version: Optional[str] = None,
        ssl_verify: Optional[Union[bool, str]] = None,
        extra_headers: Optional[Union[str, dict]] = None,
        hash_hostname: Optional[bool] = None,
        proxy_servers: Optional[MutableMapping[str, str]] = None,
        client_cert: Optional[str] = None,
        client_cert_key: Optional[str] = None,
    ):
        super().__init__()

        # Prepare the requested or default site config
        if isinstance(site, AnacondaAuthSite):
            config = site
        elif site:
            config = AnacondaAuthConfig(site=site)
        else:
            config = AnacondaAuthConfig()

        # Prepare site overrides
        if base_uri and domain:
            raise ValueError("Can only specify one of `domain` or `base_uri` argument")

        kwargs: Dict[str, Any] = {}
        if domain is not None:
            kwargs["domain"] = domain
        if auth_domain_override is not None:
            kwargs["auth_domain_override"] = auth_domain_override
        if api_key is not None:
            kwargs["api_key"] = api_key
        if ssl_verify is not None:
            kwargs["ssl_verify"] = ssl_verify
        if extra_headers is not None:
            kwargs["extra_headers"] = extra_headers
        if hash_hostname is not None:
            kwargs["hash_hostname"] = hash_hostname
        if proxy_servers is not None:
            kwargs["proxy_servers"] = proxy_servers
        if client_cert_key is not None:
            kwargs["client_cert"] = client_cert
            kwargs["client_cert_key"] = client_cert_key
        if client_cert is not None:
            kwargs["client_cert"] = client_cert

        self.config = config.model_copy(update=kwargs, deep=True)

        self.proxies = self.config.proxy_servers or {}
        self.configure_ssl()

        # base_url overrides domain
        self._base_uri = base_uri or f"https://{self.config.domain}"
        self.headers["User-Agent"] = user_agent or self._user_agent
        self.headers["X-Client-Hostname"] = get_hostname(hash=self.config.hash_hostname)
        self.api_version = api_version or self._api_version
        if self.api_version:
            self.headers["Api-Version"] = self.api_version

        if self.config.extra_headers is not None:
            if isinstance(self.config.extra_headers, str):
                try:
                    self.config.extra_headers = cast(
                        dict, json.loads(self.config.extra_headers)
                    )
                except json.decoder.JSONDecodeError:
                    raise ValueError(
                        f"{repr(self.config.extra_headers)} is not valid JSON."
                    )

            keys_to_add = self.config.extra_headers.keys() - self.headers.keys()
            for k in keys_to_add:
                self.headers[k] = self.config.extra_headers[k]

        self.auth = BearerAuth(domain=self.config.domain, api_key=self.config.api_key)
        self.hooks["response"].append(login_required)

    def configure_ssl(self) -> None:
        ssl_context = None

        if self.config.ssl_verify == "truststore":
            try:
                import ssl

                import truststore  # type: ignore

                ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

            except ImportError:
                raise AnacondaConfigValidationError(
                    "The `ssl_verify: truststore` setting is only supported on Python 3.10 or later."
                )
            self.verify = True
        else:
            self.verify = self.config.ssl_verify

        http_adapter = HTTPAdapter(ssl_context=ssl_context)
        self._ssl = ssl_context

        self.mount("http://", http_adapter)
        self.mount("https://", http_adapter)

        if self.config.client_cert_key and self.config.client_cert:
            self.cert = (self.config.client_cert, self.config.client_cert_key)
        elif self.config.client_cert:
            self.cert = self.config.client_cert

    def urljoin(self, url: str) -> str:
        return urljoin(self._base_uri, url)

    def prepare_request(self, request: requests.Request) -> PreparedRequest:
        request.url = self.urljoin(str(request.url))
        return super().prepare_request(request)

    def request(
        self,
        method: Union[str, bytes],
        url: Union[str, bytes],
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        joined_url = self.urljoin(str(url))

        # Ensure we don't set `verify` twice. If it is passed as a kwarg to this method,
        # that becomes the value. Otherwise, we use the value in `self.config.ssl_verify`.
        kwargs.setdefault("verify", self.config.ssl_verify)

        response = super().request(method, joined_url, *args, **kwargs)

        min_api_version_string = response.headers.get("Min-Api-Version")
        self._validate_api_version(min_api_version_string)

        return response

    @cached_property
    def account(self) -> dict:
        res = self.get("/api/account")
        res.raise_for_status()
        account = res.json()
        return account

    @property
    def name(self) -> str:
        user = self.account.get("user", {})

        first_name = user.get("first_name", "")
        last_name = user.get("last_name", "")
        if not first_name and not last_name:
            return self.email
        else:
            return f"{first_name} {last_name}".strip()

    @property
    def email(self) -> str:
        value = self.account.get("user", {}).get("email")
        if value is None:
            raise ValueError(
                "Something is wrong with your account. An email address could not be found."
            )
        else:
            return value

    @cached_property
    def avatar(self) -> Union[bytes, None]:
        hashed = md5(self.email.encode("utf-8")).hexdigest()
        res = self.get(
            f"https://gravatar.com/avatar/{hashed}.png?size=120&d=404",
            verify=self.config.ssl_verify,
            auth=False,  # type: ignore
        )
        if res.ok:
            return res.content
        else:
            return None

    def _validate_api_version(self, min_api_version_string: Optional[str]) -> None:
        """Validate that the client API version against the min API version from the service."""
        if min_api_version_string is None or self.api_version is None:
            return None

        # Convert to optional Version objects
        api_version = _parse_semver_string(self.api_version)
        min_api_version = _parse_semver_string(min_api_version_string)

        if api_version is None or min_api_version is None:
            return None

        if api_version < min_api_version:
            warnings.warn(
                f"Client API version is {self.api_version}, minimum supported API version is {min_api_version_string}. "
                "You may need to update your client.",
                DeprecationWarning,
            )


def _parse_semver_string(version: str) -> Optional[Version]:
    """Parse a version string into a semver Version object, stripping off any leading zeros from the components.

    If the version string is invalid, returns None.

    """
    norm_version = ".".join(s.lstrip("0") for s in version.split("."))
    try:
        return Version.parse(norm_version)
    except ValueError:
        return None


def client_factory(
    user_agent: Optional[str], api_version: Optional[str] = None
) -> BaseClient:
    return BaseClient(user_agent=user_agent, api_version=api_version)
