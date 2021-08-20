"""
Implement PEP 660, plus the existing setuptools PEP 517 hooks.
"""
from typing import Any, List, Mapping, Optional

import setuptools.build_meta
from setuptools.build_meta import *  # noqa


# metadata_directory has been removed from the PEP
def build_editable(
    wheel_directory: str,
    config_settings: Optional[Mapping[str, Any]] = None,
    metadata_directory: Optional[str] = None,
) -> str:
    return setuptools.build_meta._BACKEND._build_with_temp_dir(
        ["editable_wheel"], ".whl", wheel_directory, config_settings
    )


def get_requires_for_build_editable(
    config_settings: Optional[Mapping[str, Any]] = None
) -> List[str]:
    return []
