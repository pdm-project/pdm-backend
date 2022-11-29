from __future__ import annotations

import ast
import contextlib
import functools
import importlib
import os
import re
import sys
import warnings
from pathlib import Path
from typing import Any, Generator

from pdm.backend.exceptions import ConfigError, PDMWarning, ValidationError
from pdm.backend.hooks.base import Context
from pdm.backend.hooks.version.scm import get_version_from_scm

_attr_regex = re.compile(r"([\w.]+)\s*:\s*([\w.]+)\s*(\([^)]+\))?")


@contextlib.contextmanager
def patch_sys_path(path: str | Path) -> Generator[None, None, None]:
    old_path = sys.path[:]
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path[:] = old_path


class DynamicVersionBuildHook:
    """Dynamic version implementation.

    Currently supports `file` and `scm` sources.
    """

    supported_sources = ("file", "scm", "call")

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
            warnings.warn(
                f"Invalid version source {source}, must be one of "
                f"{', '.join(self.supported_sources)}",
                PDMWarning,
            )
            return
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
        matched = _attr_regex.match(getter)
        if matched is None:
            raise ConfigError(
                "Invalid version getter, must be in the format of "
                "`module:attribute`."
            )
        with patch_sys_path(context.root):
            module = importlib.import_module(matched.group(1))
            attrs = matched.group(2).split(".")
            obj: Any = functools.reduce(getattr, attrs, module)
            args_group = matched.group(3)
            if args_group:
                args = ast.literal_eval(args_group)
            else:
                args = ()
            version = obj(*args)
        self._write_version(context, version, write_to, write_template)
        return version
