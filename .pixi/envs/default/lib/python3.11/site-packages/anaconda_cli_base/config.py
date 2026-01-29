import os

from functools import cached_property
from pathlib import Path
from typing import Any
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

from pydantic_settings import BaseSettings
from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings import PyprojectTomlConfigSettingsSource
from pydantic_settings import SettingsConfigDict


def anaconda_config_path() -> Path:
    return Path(
        os.path.expandvars(
            os.path.expanduser(
                os.getenv("ANACONDA_CONFIG_TOML", "~/.anaconda/config.toml")
            )
        )
    )


class AnacondaBaseSettings(BaseSettings):

    def __init_subclass__(
        cls, plugin_name: Optional[Union[str, tuple]] = None, **kwargs: Any
    ) -> None:
        base_env_prefix: str = "ANACONDA_"
        pyproject_toml_table_header: Tuple[str, ...]

        if plugin_name is None:
            pyproject_toml_table_header = ()
            env_prefix = base_env_prefix
        if isinstance(plugin_name, tuple):
            if not all(isinstance(entry, str) for entry in plugin_name):
                raise ValueError(f"plugin_name={plugin_name} error: All values must be strings.")
            pyproject_toml_table_header = ("plugin", *plugin_name)
            env_prefix = base_env_prefix + "_".join(plugin_name).upper() + "_"
        elif isinstance(plugin_name, str):
            pyproject_toml_table_header = ("plugin", plugin_name)
            env_prefix = base_env_prefix + f"{plugin_name.upper()}_"
        else:
            raise ValueError(f"plugin_name={plugin_name} is not supported. It must be either a str or tuple.")

        cls.model_config = SettingsConfigDict(
            env_file=".env",
            pyproject_toml_table_header=pyproject_toml_table_header,
            env_prefix=env_prefix,
            env_nested_delimiter="__",
            extra="ignore",
            ignored_types=(cached_property,),
        )

        return super().__init_subclass__(**kwargs)

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
            dotenv_settings,
            file_secret_settings,
            PyprojectTomlConfigSettingsSource(settings_cls, anaconda_config_path()),
        )
