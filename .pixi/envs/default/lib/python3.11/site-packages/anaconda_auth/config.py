import warnings
from functools import cached_property
from typing import Any
from typing import ClassVar
from typing import Dict
from typing import Generator
from typing import Iterator
from typing import KeysView
from typing import List
from typing import Literal
from typing import MutableMapping
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union
from typing import cast
from urllib.parse import urljoin

from pydantic import BaseModel
from pydantic import Field
from pydantic import RootModel
from pydantic import field_validator
from pydantic import model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings
from pydantic_settings import PydanticBaseSettingsSource
from typing_extensions import Self

from anaconda_auth import __version__ as version
from anaconda_auth.exceptions import UnknownSiteName
from anaconda_cli_base.config import AnacondaBaseSettings
from anaconda_cli_base.config import AnacondaConfigTomlSettingsSource
from anaconda_cli_base.config import anaconda_config_path
from anaconda_cli_base.console import console


def _raise_deprecated_field_set_warning(set_fields: Dict[str, Any]) -> None:
    fields_str = ", ".join(sorted(f'"{s}"' for s in set_fields.keys()))
    warning_text = (
        "The following fields have been set using legacy environment variables "
        + "prefixed with 'ANACONDA_CLOUD_` or in the `plugins.cloud` section "
        + f"of `~/.anaconda/config.toml`: {fields_str}\n\n"
        + "Please either rename environment variables to the corresponding "
        + "`ANACONDA_AUTH_` version, or replace the `plugins.cloud` section "
        + "of the config file with `plugins.auth`."
    )
    console.print(f"[red]{warning_text}[/red]")
    warnings.warn(
        warning_text,
        DeprecationWarning,
    )


class AnacondaAuthSite(BaseModel):
    site: Optional[str] = Field(default=None, exclude=True)
    preferred_token_storage: Literal["system", "anaconda-keyring"] = "anaconda-keyring"
    domain: str = "anaconda.com"
    auth_domain_override: Optional[str] = None
    api_key: Optional[str] = None
    keyring: Optional[Dict[str, Dict[str, str]]] = None
    ssl_verify: Union[bool, str] = True
    extra_headers: Optional[Union[Dict[str, str], str]] = None
    client_id: str = "b4ad7f1d-c784-46b5-a9fe-106e50441f5a"
    redirect_uri: str = "http://127.0.0.1:8000/auth/oidc"
    openid_config_path: str = "/.well-known/openid-configuration"
    oidc_request_headers: Dict[str, str] = {"User-Agent": f"anaconda-auth/{version}"}
    login_success_path: str = "/app/local-login-success"
    login_error_path: str = "/app/local-login-error"
    use_unified_repo_api_key: bool = False
    hash_hostname: bool = True
    proxy_servers: Optional[MutableMapping[str, str]] = None
    client_cert: Optional[str] = None
    client_cert_key: Optional[str] = None
    use_device_flow: bool = False
    _merged: bool = False

    @model_validator(mode="after")
    def set_site_name_if_none(self) -> Self:
        if self.site is None:
            self.site = self.domain

        return self

    @field_validator("ssl_verify", mode="before")
    @classmethod
    def validate_ssl_verify(cls, value: Any) -> Any:
        if not isinstance(value, (bool, str)):
            raise ValueError("Must be bool or str")
        # Convert environment variable booleans
        if value == "0":
            return False
        elif value == "1":
            return True
        else:
            return value

    @property
    def auth_domain(self) -> str:
        """The authentication domain base URL.

        Defaults to the `auth` subdomain of the main domain.

        """
        if self.auth_domain_override:
            return self.auth_domain_override
        return self.domain

    @property
    def well_known_url(self) -> str:
        """The URL from which to load the OpenID configuration."""
        return urljoin(f"https://{self.auth_domain}", self.openid_config_path)

    @property
    def login_success_url(self) -> str:
        """The location to redirect after auth flow, if successful."""
        return urljoin(f"https://{self.domain}", self.login_success_path)

    @property
    def login_error_url(self) -> str:
        """The location to redirect after auth flow, if there is an error."""
        return urljoin(f"https://{self.domain}", self.login_error_path)

    @property
    def oidc(self) -> "OpenIDConfiguration":
        """The OIDC configuration, cached as a regular instance attribute."""
        from anaconda_auth.client import BaseClient

        client = BaseClient(site=self)
        res = client.get(
            self.well_known_url,
            auth=False,  # type: ignore
        )
        res.raise_for_status()
        oidc_config = OpenIDConfiguration(**res.json())
        return self.__dict__.setdefault("_oidc", oidc_config)

    @cached_property
    def aau_token(self) -> Union[str, None]:
        # The token is cached in anaconda_anon_usage, so we can also cache here
        try:
            from anaconda_anon_usage.tokens import token_string
        except ImportError:
            return None

        try:
            return token_string()
        except Exception:
            # We don't want this to block user login in any case,
            # so let any Exceptions pass silently.
            return None


class AnacondaSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        # Nothing to do here. Only implement the return statement to make mypy happy
        return None, "", False


class CondaContextSettingsSource(AnacondaSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        self.enabled = not settings_cls.model_config.get("disable_conda_context", False)

    def __call__(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        if not self.enabled:
            return values

        try:
            from conda.base.context import Context

            context = Context()

            if context.proxy_servers:
                values["proxy_servers"] = dict(context.proxy_servers)
            if context.client_ssl_cert:
                values["client_cert"] = context.client_ssl_cert
            if context.client_ssl_cert_key:
                values["client_cert_key"] = context.client_ssl_cert_key

            values["ssl_verify"] = context.ssl_verify

        except ImportError:
            pass

        return values


class AnacondaCloudSettingsSource(AnacondaSettingsSource):
    def __call__(self) -> Dict[str, Any]:
        cloud_config = AnacondaCloudConfig(raise_deprecation_warning=False)
        set_fields = cloud_config.model_dump(exclude_unset=True)
        if set_fields:
            _raise_deprecated_field_set_warning(set_fields)
        return set_fields


class AnacondaSiteSettingsSource(AnacondaSettingsSource):
    def __call__(self) -> Dict[str, Any]:
        state = self.current_state
        site_config = AnacondaAuthSitesConfig()
        all_sites = site_config.sites
        if state.get("site"):
            # If an explicit site is requested, the name must
            # be an exact match for a key in the sites data.
            site = all_sites._find_key(state["site"])
        elif state.get("domain"):
            # If a domain is requested:
            # - if a single match is found, use it
            # - if multiple matches are found, raise an error
            # - if no match is found, use the default
            try:
                site = all_sites._find_domain(state["domain"])
            except UnknownSiteName:
                return {}
        else:
            # We now fall back to default_site, which for historical
            # reasons can be a site key or a domain.
            site = all_sites._find_at(site_config.default_site)
        config = all_sites.root[site]
        values = config.model_dump(exclude_unset=True)
        values["site"] = config.site
        return values


class AnacondaAuthConfig(AnacondaAuthSite, AnacondaBaseSettings, plugin_name="auth"):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            file_secret_settings,
            dotenv_settings,
            AnacondaSiteSettingsSource(cls),
            AnacondaCloudSettingsSource(cls),
            AnacondaConfigTomlSettingsSource(settings_cls, anaconda_config_path()),
            CondaContextSettingsSource(cls),
        )


class OpenIDConfiguration(BaseModel):
    authorization_endpoint: str
    token_endpoint: str
    device_authorization_endpoint: Optional[str] = None


_OLD_OIDC_REQUEST_HEADERS = {"User-Agent": f"anaconda-cloud-auth/{version}"}


class AnacondaCloudConfig(AnacondaAuthSite, AnacondaBaseSettings, plugin_name="cloud"):
    oidc_request_headers: Dict[str, str] = _OLD_OIDC_REQUEST_HEADERS

    def __init__(self, raise_deprecation_warning: bool = True, **kwargs: Any):
        if self.__class__ == "AnacondaCloudConfig" and raise_deprecation_warning:
            warnings.warn(
                "AnacondaCloudConfig is deprecated, please use AnacondaAuthConfig instead.",
                DeprecationWarning,
            )
        super().__init__(**kwargs)


class Sites(RootModel[Dict[str, AnacondaAuthSite]]):
    def _find_key(self, key: Optional[str]) -> str:
        if key in self.root:
            return key
        raise UnknownSiteName(
            f"The site name {key} has not been configured in {anaconda_config_path()}"
        )

    def _find_domain(self, domain: Optional[str]) -> str:
        matches = [
            (key, site) for key, site in self.root.items() if site.domain == domain
        ]
        if len(matches) == 1:
            return matches[0][0]
        if matches:
            mstr = ", ".join(skey for skey, _ in matches)
            raise ValueError(
                f"The domain {domain} matches more than one configured site ({mstr})"
            )
        elif domain == "anaconda.com":
            self.root[domain] = AnacondaAuthSite()
            return domain
        else:
            raise UnknownSiteName(
                f"The site or domain {domain} has not been configured in {anaconda_config_path()}"
            )

    def _find_at(self, key: Optional[str]) -> str:
        # Fuzzy match:
        # - If the key is an exact match for a site key, use it
        # - If the key matches a single site's domain, use it
        # - Otherwise, raise an exception
        try:
            return self._find_key(key)
        except UnknownSiteName:
            return self._find_domain(key)

    def __getitem__(self, key: str) -> AnacondaAuthConfig:
        lookup = self._find_at(key)
        return AnacondaAuthConfig(site=lookup)

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        yield from self.root.__iter__()

    def __len__(self) -> int:
        return len(self.root)

    def keys(self) -> KeysView[str]:
        return self.root.keys()

    def items(self) -> Generator[Tuple[str, AnacondaAuthSite], None, None]:
        for k in self.keys():
            yield (k, self[k])

    def values(self) -> Generator[AnacondaAuthSite, None, None]:
        for k in self.keys():
            yield self[k]


class AnacondaAuthSitesConfig(AnacondaBaseSettings, plugin_name=None):
    _instance: ClassVar[Optional["AnacondaAuthSitesConfig"]] = None

    default_site: Optional[str] = None
    sites: Sites = Sites({})

    def __new__(cls, **kwargs: Any) -> "AnacondaAuthSitesConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if self.default_site is None:
            if self.sites.root:
                self.default_site = next(iter(self.sites.root))
            else:
                self.default_site = "anaconda.com"
                self.sites.root["anaconda.com"] = AnacondaAuthSite()
        for key, value in self.sites.root.items():
            value.site = key

    @classmethod
    def all_sites(cls) -> List[str]:
        return list(cls().sites.root)

    @classmethod
    def load_site(cls, site: Optional[str] = None) -> AnacondaAuthSite:
        """Load the site configuration object (site=None loads default_site)"""
        config = cls()
        sstr: str = site or config.default_site or "anaconda.com"
        return config.sites[sstr]

    def add(self, site: AnacondaAuthSite, name: Optional[str] = None) -> None:
        if name:
            key = name
        else:
            key = cast(str, site.site)

        self.sites.root[key] = site

    def remove(self, name: str) -> None:
        key = self.sites._find_at(name)

        del self.sites.root[key]

        if not self.sites.root:
            self.sites.root["anaconda.com"] = AnacondaAuthSite()

        if self.default_site == key:
            self.default_site = next(iter(self.sites.root))
