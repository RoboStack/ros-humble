import os
import re
import sys
import tempfile
from collections import deque

from copy import deepcopy
from functools import cached_property, reduce
from pathlib import Path
from shutil import copy
from tomlkit.toml_document import TOMLDocument
from typing import Any
from typing import ClassVar
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

import tomlkit
from pydantic import ValidationError
from pydantic_settings import BaseSettings
from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings import PyprojectTomlConfigSettingsSource
from pydantic_settings import SettingsConfigDict

from anaconda_cli_base.exceptions import (
    AnacondaConfigTomlSyntaxError,
    AnacondaConfigValidationError,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def anaconda_secrets_dir() -> Optional[Path]:
    path = Path(
        os.path.expandvars(
            os.path.expanduser(os.getenv("ANACONDA_SECRETS_DIR", "/run/secrets"))
        )
    )
    return path if path.is_dir() else None


def anaconda_config_path() -> Path:
    return Path(
        os.path.expandvars(
            os.path.expanduser(
                os.getenv("ANACONDA_CONFIG_TOML", "~/.anaconda/config.toml")
            )
        )
    )


class AnacondaConfigTomlSettingsSource(PyprojectTomlConfigSettingsSource):
    _cache: ClassVar[Dict[Path, Dict[str, Any]]] = {}

    def _read_file(self, file_path: Path) -> Dict[str, Any]:
        try:
            result = self._cache.get(file_path)
            if result is None:
                result = super()._read_file(file_path)
                self._cache[file_path] = result
            return result
        except tomllib.TOMLDecodeError as e:
            arg = f"{anaconda_config_path()}: {e.args[0]}"
            raise AnacondaConfigTomlSyntaxError(arg)


class AnacondaBaseSettings(BaseSettings):
    def __init_subclass__(
        cls, plugin_name: Optional[Union[str, tuple]] = None, **kwargs: Any
    ) -> None:
        base_env_prefix: str = "ANACONDA_"
        pyproject_toml_table_header: Tuple[str, ...]

        if plugin_name is None:
            pyproject_toml_table_header = ()
            env_prefix = base_env_prefix
        elif isinstance(plugin_name, tuple):
            if not all(isinstance(entry, str) for entry in plugin_name):
                raise ValueError(
                    f"plugin_name={plugin_name} error: All values must be strings."
                )
            pyproject_toml_table_header = ("plugin", *plugin_name)
            env_prefix = base_env_prefix + "_".join(plugin_name).upper() + "_"
        elif isinstance(plugin_name, str):
            pyproject_toml_table_header = ("plugin", plugin_name)
            env_prefix = base_env_prefix + f"{plugin_name.upper()}_"
        else:
            raise ValueError(
                f"plugin_name={plugin_name} is not supported. It must be either a str or tuple."
            )

        cls.model_config = SettingsConfigDict(
            env_file=".env",
            pyproject_toml_table_header=pyproject_toml_table_header,
            env_prefix=env_prefix,
            env_nested_delimiter="__",
            extra="ignore",
            ignored_types=(cached_property,),
            secrets_dir=anaconda_secrets_dir(),
            validate_assignment=True,
        )

        return super().__init_subclass__(**kwargs)

    def __init__(self, **kwargs: Any) -> None:
        try:
            super().__init__(**kwargs)
        except ValidationError as e:
            errors = []
            for error in e.errors():
                input_value = error["input"]
                msg = error["msg"]

                env_prefix = self.model_config.get("env_prefix", "")
                delimiter = self.model_config.get("env_nested_delimiter", "") or ""
                env_var = env_prefix + delimiter.join(
                    str(loc).upper() for loc in error["loc"]
                )

                kwarg = error["loc"][0]
                if kwarg in kwargs:
                    value = kwargs[str(kwarg)]
                    msg = f"- Error in init kwarg {e.title}({error['loc'][0]}={value})\n    {msg}"
                elif env_var in os.environ:
                    msg = f"- Error in environment variable {env_var}={input_value}\n    {msg}"
                else:
                    table_header = ".".join(
                        self.model_config.get("pyproject_toml_table_header", [])
                    )
                    key = ".".join(str(loc) for loc in error["loc"])
                    msg = f"- Error in {anaconda_config_path()} in [{table_header}] for {key} = {input_value}\n    {msg}"

                errors.append(msg)

            message = "\n" + "\n".join(errors)

            raise AnacondaConfigValidationError(message)

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
            AnacondaConfigTomlSettingsSource(settings_cls, anaconda_config_path()),
        )

    def write_config(
        self,
        preserve_existing_keys: bool = True,
        dry_run: bool = False,
    ) -> None:
        """
        Write the current configuration to the Anaconda config.toml file.

        This method writes the configuration instance to the config.toml file,
        preserving existing comments and formatting. Only non-default and non-None
        values are written. If a value is set to its default, the corresponding
        entry is removed from the config file.

        The write operation is atomic - the config file is only updated if the
        entire write succeeds, preventing corruption from interrupted writes.

        Args:
            preserve_existing_keys: If True (default) updates to existing keys in the
                config.toml file, will not remove the key if set to the default
                value. If False fields set to default value are removed from the file
            dry_run: If True, displays a diff of proposed changes without writing
                to the file. If False (default), writes changes to config.toml.

        Raises:
            ValidationError: If any attribute has been manually set to an invalid
                value that fails pydantic validation.
            OSError: If backup creation fails, config file cannot be read, or
                config directory cannot be created due to permissions or I/O errors.
            ValueError: If the existing config.toml contains invalid TOML syntax.

        Behavior:
            - Creates ~/.anaconda/config.toml if it doesn't exist
            - Creates timestamped backup (e.g., config.backup.20231218_143022.toml)
            - Keeps last 5 backups, automatically deletes older ones
            - Preserves comments and formatting in existing config
            - Only writes non-default, non-None values
            - Removes keys when values are set to their defaults
            - Validates all values before writing
            - Uses atomic write to prevent file corruption
        """
        values = self.model_dump(
            exclude_unset=False,
            exclude_defaults=True,
            exclude_none=True,
            exclude_computed_fields=True,
        )

        # save a timestamped backup of the config.toml
        config_toml = anaconda_config_path()
        if config_toml.exists():
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_path = config_toml.with_name(f"config.backup.{timestamp}.toml")
            try:
                copy(config_toml, backup_path)
            except (OSError, IOError) as e:
                raise OSError(
                    f"Failed to create backup of {config_toml} at {backup_path}: {e}"
                ) from e

            # Clean up old backups, keeping only the last 5
            try:
                backups = sorted(
                    config_toml.parent.glob("config.backup.*.toml"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                # Keep the 5 most recent backups, delete the rest
                for old_backup in backups[5:]:
                    old_backup.unlink()
            except (OSError, IOError):
                # If cleanup fails, continue anyway - backup was already created
                pass

            try:
                with open(config_toml, "rt") as f:
                    config = tomlkit.load(f)
            except (OSError, IOError) as e:
                raise OSError(f"Failed to read {config_toml}: {e}") from e
            except Exception as e:
                raise ValueError(
                    f"Failed to parse {config_toml} as TOML. "
                    f"The file may be corrupted or contain invalid TOML syntax: {e}"
                ) from e
        else:
            try:
                config_toml.parent.mkdir(parents=True, exist_ok=True)
            except (OSError, IOError) as e:
                raise OSError(
                    f"Failed to create directory {config_toml.parent}: {e}"
                ) from e
            config = tomlkit.TOMLDocument()

        to_update = deepcopy(config)

        table_header = self.model_config.get("pyproject_toml_table_header", tuple())

        if table_header:

            def nestitem(a: tomlkit.TOMLDocument, b: Any) -> Any:
                if b not in a:
                    a.add(b, tomlkit.table())
                return a[b]

            parent = reduce(nestitem, table_header, to_update)
        else:
            parent = to_update

        def deepmerge(
            orig: tomlkit.TOMLDocument,
            new: Dict[str, Any],
            full_model: Dict[str, Any],
            preserve_existing_keys: bool = True,
        ) -> None:
            stack = deque[Tuple[TOMLDocument, Dict[str, Any], Dict[str, Any]]](
                [(orig, new, full_model)]
            )
            while stack:
                current_original, current_update, current_full = stack.popleft()

                removed_keys = (
                    current_original.keys() - current_update.keys() - {"plugin"}
                )

                for k in removed_keys:
                    # If a key was already present in toml
                    # ensure that it remains set even if the
                    # new value is the default for the class
                    value = current_full.get(k, None)
                    if (value is not None) and preserve_existing_keys:
                        current_original[k] = value
                    else:
                        del current_original[k]

                for k, v in current_update.items():
                    if isinstance(v, dict):
                        if k not in current_original:
                            current_original.add(k, tomlkit.table())
                        to_append = (current_original.get(k), v, current_full.get(k))
                        stack.append(to_append)  # type: ignore
                    else:
                        current_original[k] = v

        full_dump = self.model_dump()
        deepmerge(
            parent, values, full_dump, preserve_existing_keys=preserve_existing_keys
        )

        if dry_run:
            import difflib
            import datetime as dt
            from rich.syntax import Syntax
            from anaconda_cli_base.console import console

            original = config.as_string()
            updated = to_update.as_string()

            dt_format = "%m-%d-%y %H:%M"
            config_toml = anaconda_config_path()
            if config_toml.exists():
                modified = dt.datetime.fromtimestamp(
                    config_toml.stat().st_mtime
                ).strftime(dt_format)
            else:
                modified = ""

            now = dt.datetime.now().strftime(dt_format)

            diffs = difflib.unified_diff(
                original.splitlines(False),
                updated.splitlines(False),
                fromfile=str(config_toml),
                fromfiledate=modified,
                tofile=str(config_toml),
                tofiledate=now,
                lineterm="",
            )
            diff = "\n".join(diffs)
            if not diff:
                console.print(
                    f"[bold green]No change to {anaconda_config_path()}[/bold green]"
                )
                return

            syntax = Syntax(code=diff, lexer="diff", line_numbers=False, word_wrap=True)
            console.print(syntax)
            return

        # Use atomic write to prevent corruption if write fails
        # Write to temp file in same directory, then atomically rename
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=config_toml.parent,
            prefix=".config_",
            suffix=".toml.tmp",
            text=True,
        )
        try:
            config_dump = tomlkit.dumps(to_update)
            config_dump = re.sub(r"\n+$", "\n", config_dump, flags=re.DOTALL)
            with os.fdopen(tmp_fd, "wt") as f:
                f.write(config_dump)
            # Atomic rename - if this fails, original file is untouched
            os.replace(tmp_path, config_toml)

            # ensure that any existing cache of the config.toml file
            # is cleared.
            AnacondaConfigTomlSettingsSource._cache.clear()
        except Exception:
            # Clean up temp file if write or rename failed
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
