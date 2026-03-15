from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml import YAMLError

from anaconda_auth._conda.config import CredentialType
from anaconda_cli_base import console

DEFAULT_CONDARC_PATH = Path("~/.condarc").expanduser()

yaml = YAML()


class CondaRCError(Exception):
    pass


class CondaRC:
    def __init__(self, condarc_path: Path | None = None):
        """
        Initializes the CondaRC object by attempting to open and load the contents
        of the condarc file found in the user's home directory.
        """
        self.condarc_path = condarc_path or DEFAULT_CONDARC_PATH
        self._loaded_yaml: dict[str, Any] = {}
        self.load()

    @property
    def _backup_condarc_path(self) -> Path:
        return self.condarc_path.with_suffix(".bak")

    def load(self, path: Path | None = None) -> None:
        path = path or self.condarc_path
        try:
            path.touch()
            with path.open("r") as fp:
                contents = fp.read()
        except OSError as exc:
            raise CondaRCError(f"Could not open condarc file: {exc}")

        try:
            self._loaded_yaml = yaml.load(contents) or {}
        except YAMLError as exc:
            raise CondaRCError(f"Could not parse condarc: {exc}")

    def update_channel_settings(
        self,
        channel: str,
        auth_type: str,
        username: str | None = None,
        *,
        auth_domain: str | None = None,
        credential_type: CredentialType | None = None,
    ) -> None:
        """
        Update the condarc file's "channel_settings" section
        """
        updated_settings = {
            "channel": channel,
            "auth": auth_type,
            "username": username,
            "auth_domain": auth_domain,
            "credential_type": credential_type.value if credential_type else None,
        }

        # Filter out any None values
        updated_settings = {
            key: value for key, value in updated_settings.items() if value is not None
        }

        channel_settings = self._loaded_yaml.get("channel_settings", []) or []

        # Filter out the existing channel's entry if it's there
        filter_settings = [
            settings
            for settings in channel_settings
            if settings.get("channel") != channel
        ]

        # Add the updated settings map
        filter_settings.append(updated_settings)

        self._loaded_yaml["channel_settings"] = filter_settings

    def restore(self) -> None:
        console.print(f"Restoring config from {self._backup_condarc_path}")
        self.load(self._backup_condarc_path)
        self.save()

    def backup(self) -> None:
        console.print(f"Backing up config to {self._backup_condarc_path}")
        self.save(self._backup_condarc_path)

    def save(self, path: Path | None = None) -> None:
        """Save the condarc file"""
        path = path or self.condarc_path
        try:
            with path.open("w") as fp:
                yaml.dump(self._loaded_yaml, fp)
        except OSError as exc:
            raise CondaRCError(f"Could not save file: {exc}")
