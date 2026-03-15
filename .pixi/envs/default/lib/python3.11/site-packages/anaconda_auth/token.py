import base64
import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Type
from typing import Union
from urllib.error import HTTPError

import jwt
import keyring
from keyring.backend import KeyringBackend
from keyring.backend import properties
from keyring.errors import PasswordDeleteError
from keyring.errors import PasswordSetError
from pydantic import BaseModel
from pydantic import Field

from anaconda_auth.config import AnacondaAuthConfig
from anaconda_auth.exceptions import TokenExpiredError
from anaconda_auth.exceptions import TokenNotFoundError

# Note: we can remove this if we pin keyring>=23.9.0
try:
    classproperty = properties.classproperty
except AttributeError:
    _KeyringClassMethod = Callable[[Type[KeyringBackend]], Any]

    def classproperty(method: _KeyringClassMethod) -> _KeyringClassMethod:  # type: ignore
        return properties.ClassProperty(classmethod(method))  # type: ignore


logger = logging.getLogger(__name__)

# TODO: Rename to "Anaconda" and then migrate existing
KEYRING_NAME = "Anaconda Cloud"


# Type aliases
LocalKeyringData = Dict[str, Dict[str, str]]
OrgName = str
TokenString = str


def _as_base64_string(payload: str) -> str:
    """Encode a string to a base64 string"""
    return base64.b64encode(payload.encode("utf-8")).decode("utf-8")


class NavigatorFallback(KeyringBackend):
    priority = 0.1  # type: ignore

    @classproperty
    def viable(cls) -> bool:
        try:
            import anaconda_navigator  # noqa: F401

            return True
        except ModuleNotFoundError:
            return False

    def set_password(self, service: str, username: str, password: str) -> None:
        raise PasswordSetError("This keyring cannot set passwords")

    def _get_auth_domain(self) -> str:
        from anaconda_navigator.config import CONF as navigator_config

        known_mapping = {"https://anaconda.cloud": "id.anaconda.cloud"}

        cloud_base_url: str = navigator_config.get(
            "main", "cloud_base_url", "https://anaconda.cloud"
        ).strip("/")
        return known_mapping[cloud_base_url]

    def get_password(self, service: str, username: str) -> Union[str, None]:
        try:
            from anaconda_navigator.api.nucleus.token import NucleusToken

            auth_domain = self._get_auth_domain()
        except ImportError:
            return None

        if service != KEYRING_NAME and username != auth_domain:
            return None

        token = NucleusToken.from_file()
        if token is not None:
            from anaconda_auth.actions import get_api_key
            from anaconda_auth.actions import refresh_access_token

            config = AnacondaAuthConfig(domain=auth_domain)
            if not token.valid:
                try:
                    access_token = refresh_access_token(
                        token.refresh_token, config=config
                    )
                except HTTPError:
                    return None
            else:
                access_token = token.access_token

            api_key = get_api_key(access_token)
            token_info = {
                "username": token.username,
                "api_key": api_key,
                "domain": config.domain,
            }
            payload = json.dumps(token_info)
            encoded = _as_base64_string(payload)
            keyring.set_password(KEYRING_NAME, auth_domain, encoded)

            return encoded
        return None

    def delete_password(self, service: str, username: str) -> None:
        auth_domain = self._get_auth_domain()
        try:
            from anaconda_navigator.api.nucleus.token import (
                TOKEN_FILE as navigator_token_file,
            )

        except ImportError:
            return None

        if service != KEYRING_NAME and username != auth_domain:
            return None
        else:
            try:
                os.remove(navigator_token_file)
            except FileNotFoundError:
                return None


class AnacondaKeyring(KeyringBackend):
    name = "token AnacondaKeyring"  # Pinning name explicitly instead of relying on module.submodule automatic naming convention.
    keyring_path = Path("~/.anaconda/keyring").expanduser()

    @classproperty
    def priority(cls) -> float:
        config = AnacondaAuthConfig()
        if config.preferred_token_storage == "system":
            return 0.2
        elif config.preferred_token_storage == "anaconda-keyring":
            return 11.0
        else:
            raise ValueError(
                f"token_storage: {config.preferred_token_storage} is not supported."
            )

    @classproperty
    def viable(cls) -> bool:
        try:
            cls.keyring_path.parent.mkdir(exist_ok=True, parents=True)
            with cls.keyring_path.open("a") as f:
                writable = f.writable()
            return writable
        except OSError:
            return False

    def _read(self) -> LocalKeyringData:
        if not self.keyring_path.exists():
            return {}

        try:
            with self.keyring_path.open("r") as fp:
                data = json.load(fp)
            return data
        except json.JSONDecodeError:
            return {}

    def _save(self, data: LocalKeyringData) -> None:
        self.keyring_path.parent.mkdir(exist_ok=True, parents=True)

        with self.keyring_path.open("w") as fp:
            json.dump(data, fp)

    def set_password(self, service: str, username: str, password: str) -> None:
        data = self._read()

        if service not in data:
            data[service] = {}

        data[service][username] = password

        self._save(data)

    def get_password(self, service: str, username: str) -> Union[str, None]:
        data = self._read()
        return data.get(service, {}).get(username, None)

    def delete_password(self, service: str, username: str) -> None:
        data = self._read()
        try:
            data.get(service, {}).pop(username)
            self._save(data)
        except KeyError:
            raise PasswordDeleteError


class ConfigKeyring(AnacondaKeyring):
    name = "token ConfigKeyring"

    @classproperty
    def priority(cls) -> float:
        config = AnacondaAuthConfig()
        return 100.0 if config.api_key or config.keyring else 0.0

    def set_password(self, service: str, username: str, password: str) -> None:
        raise PasswordSetError("This keyring cannot set passwords")

    def delete_password(self, service: str, username: str) -> None:
        raise PasswordSetError("This keyring cannot delete passwords")

    def _read(self) -> LocalKeyringData:
        config = AnacondaAuthConfig()
        if config.api_key:
            # Build a keyring structure out of the api key and domain
            decoded = TokenInfo(domain=config.domain, api_key=config.api_key)
            encoded = base64.b64encode(
                decoded.model_dump_json().encode("ascii")
            ).decode("ascii")
            return {KEYRING_NAME: {config.domain: encoded}}
        if config.keyring:
            return config.keyring
        return {}


class RepoToken(BaseModel):
    token: TokenString
    org_name: Union[OrgName, None] = None


# A mapping of modern domain to a list of legacy domains. If a token is searched
# for at the modern domain and not found, we will search for any of the legacy domains
# and, if found, migrate the keyring storage from that domain to the new one.
MIGRATIONS: Dict[str, List[str]] = {
    "anaconda.com": ["id.anaconda.cloud", "anaconda.cloud"]
}
TOKEN_INFO_VERSION = 2


class TokenInfo(BaseModel):
    domain: str = Field(default_factory=lambda: AnacondaAuthConfig().domain)
    api_key: Union[str, None] = None
    username: Union[str, None] = None
    repo_tokens: List[RepoToken] = []
    version: Optional[int] = TOKEN_INFO_VERSION

    @classmethod
    def _decode(cls, keyring_data: str) -> dict:
        decoded_bytes = base64.b64decode(keyring_data)
        decoded_dict = json.loads(decoded_bytes)
        return decoded_dict

    @classmethod
    def _migrate(
        cls, keyring_data: str, from_domain: str, to_domain: str
    ) -> "TokenInfo":
        """Migrate the domain and save token under new domain."""
        decoded_dict = cls._decode(keyring_data)
        decoded_dict["domain"] = to_domain
        decoded_dict["version"] = TOKEN_INFO_VERSION
        token_info = TokenInfo(**decoded_dict)
        token_info.save()
        keyring.delete_password(KEYRING_NAME, from_domain)
        logger.debug(
            f"🔓 Token has been migrated from legacy domain '{from_domain}' to '{to_domain}' 🎉"
        )
        return token_info

    @classmethod
    def load(cls, domain: Optional[str] = None, *, create: bool = False) -> "TokenInfo":
        """Load the token information from the system keyring.

        Args:
            domain: The domain for which to load the token information. If
                not provided, defaults to the configuration domain.
            create: If True, create a new TokenInfo object if not found.

        Returns:
            The token information.

        """
        domain = domain or AnacondaAuthConfig().domain

        keyring_data = keyring.get_password(KEYRING_NAME, domain)
        if keyring_data is not None:
            logger.debug("🔓 Token has been successfully retrieved from keyring 🎉")
            decoded_dict = cls._decode(keyring_data)
            return TokenInfo(**decoded_dict)

        # Try again to see if there is a legacy token on disk
        legacy_domains = MIGRATIONS.get(domain, [])
        for legacy_domain in legacy_domains:
            existing_keyring_data = keyring.get_password(KEYRING_NAME, legacy_domain)
            if existing_keyring_data is not None:
                return cls._migrate(
                    existing_keyring_data, from_domain=legacy_domain, to_domain=domain
                )

        if create:
            logger.debug("🔓 Token has been successfully created 🎉")
            return TokenInfo(domain=domain)

        raise TokenNotFoundError

    def save(self) -> None:
        """Write the token information to the system keyring."""
        payload = self.model_dump_json(exclude_none=True)
        encoded = _as_base64_string(payload)
        keyring.set_password(KEYRING_NAME, self.domain, encoded)
        logger.debug("🔒 Token has been safely stored in system keychain 🎉")

    def delete(self) -> None:
        """Delete the token information from the system keyring."""
        try:
            keyring.delete_password(KEYRING_NAME, self.domain)
            if NavigatorFallback.viable:
                NavigatorFallback().delete_password(KEYRING_NAME, self.domain)
        except PasswordDeleteError:
            raise TokenNotFoundError

    @property
    def expired(self) -> bool:
        if self.api_key is None:
            return True

        decoded = jwt.decode(
            self.api_key, algorithms=["RS256"], options={"verify_signature": False}
        )
        expiry = dt.datetime.fromtimestamp(decoded["exp"]).replace(
            tzinfo=dt.timezone.utc
        )
        return expiry < dt.datetime.now(tz=dt.timezone.utc)

    def get_access_token(self) -> str:
        """Get the access token, ensuring login and refresh if necessary."""
        if self.api_key is None:
            try:
                new_token_info = TokenInfo.load(self.domain)
            except TokenNotFoundError:
                message = "No token found, please login with `anaconda login`"
                raise TokenNotFoundError(message)

            # Store the new token information for later retrieval
            self.username = new_token_info.username
            self.api_key = new_token_info.api_key

        assert self.api_key is not None

        if self.expired:
            raise TokenExpiredError(
                "Your login token as expired. Please login again using\n"
                "  anaconda login --force"
            )

        return self.api_key

    def set_repo_token(self, org_name: OrgName, token: TokenString) -> None:
        """Set the repo token for a specific organization.

        Args:
            org_name: The organization name for which to search for a token.
            token: The token value.

        """

        try:
            self.get_repo_token(org_name=org_name)
        except TokenNotFoundError:
            # This is good, we don't need to do anything
            pass
        else:
            # We need to remove the existing token for this org first
            # TODO: We can drop this once we just use a dictionary instead
            self.repo_tokens[:] = [
                t for t in self.repo_tokens if t.org_name != org_name
            ]

        self.repo_tokens.append(RepoToken(org_name=org_name, token=token))

    def get_repo_token(self, org_name: OrgName) -> TokenString:
        """Return the installed repo token for a specific organization.

        Args:
            org_name: The organization name for which to search for a token.

        Returns:
            The repo access token associated with the requested organization.

        Raises:
            TokenNotFoundError: if no token is found in the keyring for that organization.

        """
        for token in self.repo_tokens:
            if token.org_name == org_name:
                return token.token
        raise TokenNotFoundError(f"Could not find repo token for org {org_name}")

    def delete_repo_token(self, org_name: OrgName) -> None:
        """Delete the repo token for a specific organization.

        Args:
            org_name: The organization name for which to delete a token.

        """
        # TODO: Confirm whether we should raise an exception or not if token doesn't exist for specified organization

        # We need to remove the existing token for this org first
        # TODO: We can drop this once we just use a dictionary instead
        self.repo_tokens[:] = [t for t in self.repo_tokens if t.org_name != org_name]

    def delete_all_repo_token(self) -> None:
        """Delete all repo tokens"""

        self.repo_tokens[:] = []
