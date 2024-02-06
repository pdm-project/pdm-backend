from __future__ import annotations

import sys
from typing import Any, Mapping

from pdm.backend import build_editable as build_editable
from pdm.backend import build_sdist as build_sdist
from pdm.backend import build_wheel as build_wheel
from pdm.backend import (
    prepare_metadata_for_build_editable as prepare_metadata_for_build_editable,
)
from pdm.backend import (
    prepare_metadata_for_build_wheel as prepare_metadata_for_build_wheel,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import pdm.backend._vendor.tomli as tomllib


def get_requires_for_build_wheel(
    config_settings: Mapping[str, Any] | None = None,
) -> list[str]:
    with open("pyproject.toml", "rb") as fp:
        config = tomllib.load(fp)
    return config["project"].get("dependencies", [])


get_requires_for_build_sdist = get_requires_for_build_wheel


def get_requires_for_build_editable(
    config_settings: Mapping[str, Any] | None = None,
) -> list[str]:
    return get_requires_for_build_wheel(config_settings) + ["editables"]
