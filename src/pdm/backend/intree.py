from __future__ import annotations

import sys
from typing import Any, Mapping

import pdm.backend as api

if sys.version_info >= (3, 11):
    import tomllib
else:
    import pdm.backend._vendor.tomli as tomllib


def get_requires_for_build_wheel(
    config_settings: Mapping[str, Any] | None = None
) -> list[str]:
    with open("pyproject.toml", "rb") as fp:
        config = tomllib.load(fp)
    return config["project"].get("dependencies", [])


get_requires_for_build_sdist = get_requires_for_build_wheel


def get_requires_for_build_editable(
    config_settings: Mapping[str, Any] | None = None
) -> list[str]:
    return get_requires_for_build_wheel(config_settings) + ["editables"]


def __getattr__(name: str) -> Any:
    return getattr(api, name)
