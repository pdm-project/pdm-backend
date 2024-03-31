from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Callable

from pdm.backend.exceptions import ConfigError, PDMWarning, ValidationError
from pdm.backend.hooks.base import Context
from pdm.backend.hooks.version.scm import SCMVersion as SCMVersion
from pdm.backend.hooks.version.scm import get_version_from_scm
from pdm.backend.utils import evaluate_module_attribute


class DynamicVersionBuildHook:
    """Dynamic version implementation.

    Currently supports `file` and `scm` sources.
    """

    def pdm_build_initialize(self, context: Context) -> None:
        version_config = (
            context.config.data.get("tool", {}).get("pdm", {}).get("version", {})
        )
        metadata = context.config.metadata
        if not version_config or "version" in metadata:
            if metadata.get("version") is None:
                metadata["version"] = "0.0.0"
            try:
                metadata["dynamic"].remove("version")
            except (ValueError, KeyError):
                pass
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
        if source not in _SUPPORTED_SOURCES:
            warnings.warn(
                f"Invalid version source {source}, must be one of "
                f"{', '.join(_SUPPORTED_SOURCES.keys())}",
                PDMWarning,
            )
            return
        options = {k: v for k, v in version_config.items() if k != "source"}
        metadata["version"] = _SUPPORTED_SOURCES[source](self, context, **options)
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
        tag_regex: str | None = None,
        version_format: str | None = None,
        fallback_version: str | None = None,
    ) -> str:
        if "PDM_BUILD_SCM_VERSION" in os.environ:
            version = os.environ["PDM_BUILD_SCM_VERSION"]
        else:
            if version_format is not None:
                version_formatter, _ = evaluate_module_attribute(
                    version_format, context.root
                )
            else:
                version_formatter = None
            version = get_version_from_scm(
                context.root, tag_regex=tag_regex, version_formatter=version_formatter
            )
            if version is None:
                if fallback_version is not None:
                    version = fallback_version
                else:
                    raise ConfigError(
                        "Cannot find the version from SCM or SCM isn't detected. \n"
                        "You can still specify the version via environment variable "
                        "`PDM_BUILD_SCM_VERSION`, or specify `fallback_version` config."
                    )

        self._write_version(context, version, write_to, write_template)
        return version

    def _write_version(
        self,
        context: Context,
        version: str,
        write_to: str | None = None,
        write_template: str = "{}\n",
    ) -> None:
        """Write the resolved version to the file."""
        if write_to is not None:
            if context.target == "sdist" and context.config.build_config.package_dir:
                write_to = os.path.join(
                    context.config.build_config.package_dir, write_to
                )
            if context.target == "editable":
                target = Path(context.config.build_config.package_dir or ".") / write_to
            else:
                target = context.build_dir / write_to
            if not target.parent.exists():
                target.parent.mkdir(0o700, parents=True)
            with open(target, "w", encoding="utf-8", newline="") as fp:
                fp.write(write_template.format(version))

    def resolve_version_from_call(
        self,
        context: Context,
        getter: str,
        write_to: str | None = None,
        write_template: str = "{}\n",
    ) -> str:
        version_getter, args = evaluate_module_attribute(getter, context.root)
        version = version_getter(*args)
        self._write_version(context, version, write_to, write_template)
        return version


_SUPPORTED_SOURCES: dict[str, Callable[..., str]] = {
    "file": DynamicVersionBuildHook.resolve_version_from_file,
    "scm": DynamicVersionBuildHook.resolve_version_from_scm,
    "call": DynamicVersionBuildHook.resolve_version_from_call,
}
