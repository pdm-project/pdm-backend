from __future__ import annotations

import os
import re

from pdm.backend.exceptions import ConfigError, ValidationError
from pdm.backend.hooks.base import Context
from pdm.backend.hooks.version.scm import get_version_from_scm


class DynamicVersionBuildHook:
    """Dynamic version implementation.

    Currently supports `file` and `scm` sources.
    """

    supported_sources = ("file", "scm")

    def pdm_build_initialize(self, context: Context) -> None:
        version_config = (
            context.config.data.get("tool", {}).get("pdm", {}).get("version", {})
        )
        metadata = context.config.metadata
        if not version_config or "version" in metadata:
            if metadata.get("version") is None:
                metadata["version"] = "0.0.0"
            return
        if "version" not in metadata.get("dynamic", []):
            raise ValidationError(
                "missing 'version' in project.dynamic",
                "The 'version' field must be present in project.dynamic to "
                "resolve it dynamically",
            )
        source: str = version_config.get("source")
        if not source:
            raise ConfigError("tool.pdm.version.source is required")
        if source not in self.supported_sources:
            raise ConfigError(
                f"Invalid version source {source}, must be one of "
                f"{', '.join(self.supported_sources)}"
            )
        options = {k: v for k, v in version_config.items() if k != "source"}
        metadata["version"] = getattr(self, f"resolve_version_from_{source}")(
            context, **options
        )
        metadata["dynamic"].remove("version")

    def resolve_version_from_file(self, context: Context, path: str) -> str:
        """Resolve version from a file."""
        version_source = context.root / path
        with open(version_source, encoding="utf-8") as fp:
            match = re.search(
                r"^__version__\s*=\s*[\"'](.+?)[\"']\s*(?:#.*)?$", fp.read(), re.M
            )
        if not match:
            raise ConfigError(
                f"Couldn't find version in file {version_source!r}, "
                "it should appear as `__version__ = 'a.b.c'`.",
            )
        return match.group(1)

    def resolve_version_from_scm(
        self,
        context: Context,
        write_to: str | None = None,
        write_template: str = "{}\n",
    ) -> str:
        if "PDM_BUILD_SCM_VERSION" in os.environ:
            version = os.environ["PDM_BUILD_SCM_VERSION"]
        else:
            version = get_version_from_scm(context.root)
        if write_to is not None:
            target = context.build_dir / write_to
            if not target.parent.exists():
                target.parent.mkdir(0o700, parents=True)
            with open(target, "w", encoding="utf-8", newline="") as fp:
                fp.write(write_template.format(version))
        return version
