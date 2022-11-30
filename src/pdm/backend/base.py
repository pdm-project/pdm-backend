from __future__ import annotations

import glob
import os
import shutil
import sys
import warnings
from pathlib import Path
from typing import Any, Iterable, Mapping, TypeVar, cast

from pdm.backend.config import Config
from pdm.backend.exceptions import PDMWarning, ValidationError
from pdm.backend.hooks import BuildHookInterface, Context
from pdm.backend.hooks.version import DynamicVersionBuildHook
from pdm.backend.structures import FileMap
from pdm.backend.utils import cd, import_module_at_path, is_python_package

if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points

METADATA_BASE = """\
Metadata-Version: 2.1
Name: {name}
Version: {version}
"""

T = TypeVar("T", bound="Builder")


def is_same_or_descendant_path(target: str, path: str) -> bool:
    """Check target is same or descendant with path"""
    try:
        Path(target).relative_to(path)
        return True
    except ValueError:
        return False


def _merge_globs(
    include_globs: dict[str, str], excludes_globs: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Correctly merge includes and excludes.
    When a pattern exists in both includes and excludes,
    determine the priority in the following ways:

    1. The one with more parts in the path wins
    2. If part numbers are equal, the one that is more concrete wins
    3. If both have the same part number and concrete level, *excludes* wins
    """

    def path_weight(pathname: str) -> tuple[int, int]:
        """Return a two-element tuple [part_num, concrete_level]"""
        pathname_parts = Path(pathname).parts
        wildcard_count = 0
        if glob.has_magic(pathname):
            for part in pathname_parts:
                if part == "**":
                    wildcard_count += 2
                elif glob.has_magic(part):
                    wildcard_count += 1
        # The concrete level is the opposite of wildcard_count
        return len(pathname_parts), -wildcard_count

    includes = []
    for path, key in include_globs.items():
        if path in excludes_globs:
            if path_weight(key) <= path_weight(excludes_globs[path]):
                continue  # Exclude wins
            else:
                del excludes_globs[path]  # Include wins
        includes.append(path)
    return includes, list(excludes_globs)


def _find_top_packages(root: str) -> list[str]:
    result = []
    for path in os.listdir(root):
        path = os.path.join(root, path)
        if is_python_package(path):
            result.append(path)
    return result


class Builder:
    """Base class for building and distributing a package from given path."""

    DEFAULT_EXCLUDES = ["build"]

    target: str
    hooks: list[BuildHookInterface] = [DynamicVersionBuildHook()]

    def __init__(
        self,
        location: str | Path,
        config_settings: Mapping[str, Any] | None = None,
    ) -> None:
        self._old_cwd: str | None = None
        self.location = Path(location)
        self.config = Config.from_pyproject(self.location)
        self.config_settings = dict(config_settings or {})
        self._hooks = list(self.get_hooks())

    def get_hooks(self) -> Iterable[BuildHookInterface]:
        """Load hooks in the following order:

        1. plugins installed in 'pdm.build.hook' entry point group.
        2. local hook defined in the `pdm_build.py` file.
        """
        yield from self.hooks
        for ep in entry_points(group="pdm.build.hook"):
            hook = ep.load()
            try:
                yield cast(BuildHookInterface, hook())  # for a hook class
            except TypeError:
                yield cast(BuildHookInterface, hook)  # for a hook module
        local_hook = self.config.build_config.custom_hook
        if local_hook is not None:
            yield cast(
                BuildHookInterface, import_module_at_path(self.location / local_hook)
            )

    def call_hook(
        self, hook_name: str, context: Context, *args: Any, **kwargs: Any
    ) -> None:
        """Call the hook on all registered hooks and skip if not implemented."""
        for hook in self._hooks:
            if hasattr(hook, "pdm_build_hook_enabled"):
                if not hook.pdm_build_hook_enabled(context):
                    continue
            if hasattr(hook, hook_name):
                getattr(hook, hook_name)(context, *args, **kwargs)

    def build_context(self, destination: Path, **kwargs: Any) -> Context:
        build_dir = self.location / "build"
        if not destination.exists():
            destination.mkdir(0o700, parents=True)
        return Context(
            root=self.location,
            config=self.config,
            target=self.target,
            build_dir=build_dir,
            dist_dir=destination,
            config_settings=self.config_settings,
            kwargs=kwargs,
        )

    def __enter__(self: T) -> T:
        self._old_cwd = os.getcwd()
        os.chdir(self.location)
        return self

    def __exit__(self, *args: Any) -> None:
        assert self._old_cwd
        os.chdir(self._old_cwd)

    def clean(self, context: Context) -> None:
        """Clean up the build directory."""
        self.call_hook("pdm_build_clean", context)
        if context.build_dir.exists():
            shutil.rmtree(context.build_dir)

    def initialize(self, context: Context) -> None:
        self.call_hook("pdm_build_initialize", context)

    def get_files(self, context: Context) -> Iterable[tuple[str, Path]]:
        """Get the files to add to the package, return a iterable of
        (relpath, path).
        """
        files = self._collect_files(context, self.location)
        self.call_hook("pdm_build_update_files", context, files)
        # At this point, all files must be ready under the build_dir,
        # collect them now.
        if context.build_dir.exists():
            files.update(self._collect_files(context, context.build_dir))
        return sorted(files.items())

    def finalize(self, context: Context, artifact: Path) -> None:
        self.call_hook("pdm_build_finalize", context, artifact)

    def build(self, build_dir: str, **kwargs: Any) -> Path:
        """Build the package and return the path to the artifact."""
        context = self.build_context(Path(build_dir), **kwargs)
        if (
            not self.config_settings.get("no-clean-build")
            or os.getenv("PDM_BUILD_NO_CLEAN", "false").lower() != "false"
        ):
            self.clean(context)
        self.initialize(context)
        files = self.get_files(context)
        artifact = self.build_artifact(context, files)
        self.finalize(context, artifact)
        return artifact

    def build_artifact(
        self, context: Context, files: Iterable[tuple[str, Path]]
    ) -> Path:
        """Build the artifact from an iterable of (relpath, path) pairs
        and return the path to it.
        """
        raise NotImplementedError()

    def format_pkginfo(self) -> str:
        metadata = self.config.as_standard_metadata()
        return str(metadata.as_rfc822())

    def _collect_files(self, context: Context, root: Path) -> FileMap:
        """Collect files to add to the artifact under the given root."""
        includes, excludes = self._get_include_and_exclude_paths(root)
        files = FileMap()
        for include_path in includes:
            path = root / include_path
            if path.is_file():
                files[include_path] = path
                continue
            # The path is a directory name
            for p in path.glob("**/*"):
                if not p.is_file():
                    continue

                rel_path = p.absolute().relative_to(root).as_posix()
                if p.name.endswith(".pyc") or self._is_excluded(rel_path, excludes):
                    continue

                files[rel_path] = p

        return files

    def find_license_files(self) -> list[str]:
        """Return a list of license files from the PEP 639 metadata."""
        root = self.location
        license_files = self.config.metadata.license_files
        if "paths" in license_files:
            invalid_paths = [
                p for p in license_files["paths"] if not (root / p).is_file()
            ]
            if invalid_paths:
                raise ValidationError(
                    "license-files", f"License files not found: {invalid_paths}"
                )
            return license_files["paths"]
        else:
            paths = [
                p.relative_to(root).as_posix()
                for pattern in license_files["globs"]
                for p in root.glob(pattern)
                if (root / p).is_file()
            ]
            if license_files["globs"] and not paths:
                warnings.warn(
                    f"No license files are matched with glob patterns "
                    f"{license_files['globs']}.",
                    PDMWarning,
                    stacklevel=2,
                )
            return paths

    def _get_include_and_exclude_paths(self, root: Path) -> tuple[list[str], list[str]]:
        includes = set()
        excludes = set(self.DEFAULT_EXCLUDES)
        build_config = self.config.build_config
        meta_excludes = list(build_config.excludes)
        source_includes = build_config.source_includes or ["tests"]
        if self.target != "sdist":
            # exclude source-includes for non-sdist builds
            meta_excludes.extend(source_includes)

        if not build_config.includes:
            top_packages = _find_top_packages(build_config.package_dir or ".")
            if top_packages:
                includes.update(top_packages)
            else:
                # Include all top-level .py modules under the package-dir
                includes.add(f"{build_config.package_dir or '.'}/*.py")
        else:
            # use what user specifies
            includes.update(build_config.includes)

        includes.update(source_includes)
        excludes.update(meta_excludes)

        with cd(root):
            include_globs = {
                os.path.normpath(path): key
                for key in includes
                for path in glob.iglob(key, recursive=True)
            }

            excludes_globs = {
                os.path.normpath(path): key
                for key in excludes
                for path in glob.iglob(key, recursive=True)
            }

        include_paths, exclude_paths = _merge_globs(include_globs, excludes_globs)
        return sorted(include_paths), sorted(exclude_paths)

    def _is_excluded(self, path: str, exclude_paths: list[str]) -> bool:
        return any(
            is_same_or_descendant_path(path, exclude_path)
            for exclude_path in exclude_paths
        )

    def _show_add_file(self, rel_path: str, full_path: Path) -> None:
        try:
            show_path = full_path.relative_to(self.location)
        except ValueError:
            show_path = full_path
        print(f" - Adding {show_path} -> {rel_path}")
