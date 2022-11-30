"""
PEP-517 compliant pyproject build-system API
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

__version__ = "2.0.0a3"


def get_requires_for_build_wheel(
    config_settings: Mapping[str, Any] | None = None
) -> list[str]:
    """
    Returns an additional list of requirements for building, as PEP508 strings,
    above and beyond those specified in the pyproject.toml file.

    When C-extension build is needed, setuptools should be required, otherwise
    just return an empty list.
    """
    from pdm.backend.wheel import WheelBuilder

    with WheelBuilder(Path.cwd(), config_settings) as builder:
        if builder.config.build_config.run_setuptools:
            return ["setuptools>=40.8.0"]
        return []


def get_requires_for_build_sdist(
    config_settings: Mapping[str, Any] | None = None
) -> list[str]:
    """There isn't any requirement for building a sdist at this point."""
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str, config_settings: Mapping[str, Any] | None = None
) -> str:
    """Prepare the metadata, places it in metadata_directory"""
    from pdm.backend.wheel import WheelBuilder

    with WheelBuilder(Path.cwd(), config_settings) as builder:
        return builder.prepare_metadata(metadata_directory).name


def build_wheel(
    wheel_directory: str,
    config_settings: Mapping[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    """Builds a wheel, places it in wheel_directory"""
    from pdm.backend.wheel import WheelBuilder

    with WheelBuilder(Path.cwd(), config_settings) as builder:
        return builder.build(
            wheel_directory, metadata_directory=metadata_directory
        ).name


def build_sdist(
    sdist_directory: str, config_settings: Mapping[str, Any] | None = None
) -> str:
    """Builds an sdist, places it in sdist_directory"""
    from pdm.backend.sdist import SdistBuilder

    with SdistBuilder(Path.cwd(), config_settings) as builder:
        return builder.build(sdist_directory).name


def get_requires_for_build_editable(
    config_settings: Mapping[str, Any] | None = None
) -> list[str]:
    """
    Returns an additional list of requirements for building, as PEP508 strings,
    above and beyond those specified in the pyproject.toml file.

    When C-extension build is needed, setuptools should be required, otherwise
    just return an empty list.
    """
    return get_requires_for_build_wheel(config_settings) + ["editables"]


def prepare_metadata_for_build_editable(
    metadata_directory: str, config_settings: Mapping[str, Any] | None = None
) -> str:
    """Prepare the metadata, places it in metadata_directory"""
    from pdm.backend.editable import EditableBuilder

    with EditableBuilder(Path.cwd(), config_settings) as builder:
        return builder.prepare_metadata(metadata_directory).name


def build_editable(
    wheel_directory: str,
    config_settings: Mapping[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    from pdm.backend.editable import EditableBuilder

    with EditableBuilder(Path.cwd(), config_settings) as builder:
        return builder.build(
            wheel_directory, metadata_directory=metadata_directory
        ).name
