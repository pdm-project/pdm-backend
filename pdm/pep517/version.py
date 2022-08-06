from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Any

from pdm.pep517.exceptions import MetadataError
from pdm.pep517.scm import get_version_from_scm


class DynamicVersion:
    """Dynamic version implementation.

    Currently supports `file` and `scm` sources.
    """

    _valid_args = {"file": ["path"], "scm": ["write_to", "write_template"]}

    def __init__(self, source: str, **options: Any) -> None:
        self.source = source
        self.options = options

    @classmethod
    def from_toml(cls, toml: dict[str, Any]) -> DynamicVersion:
        """Create a DynamicVersion from a TOML dictionary."""
        options = toml.copy()
        if "from" in options:
            source = "file"
            path = options["from"]
            warnings.warn(
                "DEPRECATED: `version = {from = ...}` is replaced by "
                '`version = {source = "file", path = ...}`',
                DeprecationWarning,
                stacklevel=2,
            )
            return cls(source, path=path)

        if "use_scm" in options:
            source = "scm"
            warnings.warn(
                "DEPRECATED: `version = {use_scm = true}` is replaced by "
                '`version = {source = "scm"}`',
                DeprecationWarning,
                stacklevel=2,
            )
            options.pop("use_scm")
        else:
            source = options.pop("source", None)

        if source not in cls._valid_args:
            raise MetadataError(
                "version",
                f"Invalid source for dynamic version: {source}, "
                f"allowed: {', '.join(cls._valid_args)}",
            )
        allowed_args = cls._valid_args[source]
        unrecognized_args = set(options) - set(allowed_args)
        if unrecognized_args:
            raise MetadataError(
                "version",
                f"Unrecognized arguments for dynamic version: {unrecognized_args}, "
                f"allowed: {', '.join(allowed_args)}",
            )
        return cls(source, **options)

    def evaluate_in_project(self, root: str | Path) -> str:
        """Evaluate the dynamic version."""
        if self.source == "file":
            version_source = os.path.join(root, self.options["path"])
            with open(version_source, encoding="utf-8") as fp:
                match = re.search(
                    r"^__version__\s*=\s*[\"'](.+?)[\"']\s*(?:#.*)?$", fp.read(), re.M
                )
                if not match:
                    raise MetadataError(
                        "version",
                        f"Can't find version in file {version_source}, "
                        "it should appear as `__version__ = 'a.b.c'`.",
                    )
                return match.group(1)
        else:
            return get_version_from_scm(root)
