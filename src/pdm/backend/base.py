from __future__ import annotations

import glob
import os
import shutil
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Literal,
    Mapping,
    TypeVar,
    cast,
)

from pdm.backend._vendor.pyproject_metadata import StandardMetadata
from pdm.backend.config import Config
from pdm.backend.hooks import BuildHookInterface, Context
from pdm.backend.hooks.version import DynamicVersionBuildHook
from pdm.backend.structures import FileMap
from pdm.backend.utils import expand_vars, import_module_at_path, is_python_package

if TYPE_CHECKING:
    from typing import SupportsIndex

if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points

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


Target = Literal["sdist", "wheel", "editable"]


class Builder:
    """Base class for building and distributing a package from given path."""

    DEFAULT_EXCLUDES = [".pdm-build"]

    target: Target
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

    def __reduce_ex__(self, __protocol: SupportsIndex = 3) -> str | tuple[Any, ...]:
        return (
            self.__class__,
            (self.location, self.config_settings),
            {"config": self.config},
        )

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
                BuildHookInterface,
                import_module_at_path(
                    self.location / local_hook, context=self.location
                ),
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
        build_dir = self.location / ".pdm-build"
        if not destination.exists():
            destination.mkdir(0o700, parents=True)
        return Context(
            build_dir=build_dir, dist_dir=destination, kwargs=kwargs, builder=self
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

    def _fix_dependencies(self) -> None:
        """Fix the dependencies and remove dynamic variables from the metadata"""
        metadata = self.config.metadata
        root = self.location.as_posix()
        if metadata.get("dependencies"):
            metadata["dependencies"] = [
                expand_vars(dep, root) for dep in metadata["dependencies"]
            ]
        if metadata.get("optional-dependencies"):
            for name, deps in metadata["optional-dependencies"].items():
                metadata["optional-dependencies"][name] = [
                    expand_vars(dep, root) for dep in deps
                ]

    def initialize(self, context: Context) -> None:
        """Initialize the build context."""
        self._fix_dependencies()
        self.call_hook("pdm_build_initialize", context)

    def get_files(self, context: Context) -> Iterable[tuple[str, Path]]:
        """Get the files to add to the package, return a iterable of
        (relpath, path).
        """
        files = self._collect_files(context)
        self.call_hook("pdm_build_update_files", context, files)
        # At this point, all files must be ready under the build_dir,
        # collect them now.
        files.update(self._collect_build_files(context))
        return files.items()

    def finalize(self, context: Context, artifact: Path) -> None:
        self.call_hook("pdm_build_finalize", context, artifact)

    def build(self, build_dir: str, **kwargs: Any) -> Path:
        """Build the package and return the path to the artifact."""
        context = self.build_context(Path(build_dir), **kwargs)
        should_clean = True

        if "no-clean-build" in self.config_settings:
            should_clean = False
        elif "PDM_BUILD_NO_CLEAN" in os.environ:
            should_clean = os.getenv("PDM_BUILD_NO_CLEAN", "0").lower() in (
                "0",
                "false",
                "no",
            )

        if should_clean:
            self.clean(context)

        self.initialize(context)
        files = sorted(self.get_files(context))
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

    def _collect_files(self, context: Context) -> FileMap:
        """Collect files to add to the artifact under the given root."""
        root = self.location
        includes, excludes = self._get_include_and_exclude_paths()
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

    def _collect_build_files(self, context: Context) -> FileMap:
        """Collect files from the build directory."""
        files = FileMap()
        if not context.build_dir.exists():
            return files
        _, excludes = self._get_include_and_exclude()
        for p in context.build_dir.glob("**/*"):
            if not p.is_file():
                continue
            rel_path = p.absolute().relative_to(context.build_dir).as_posix()
            if not self._is_excluded(rel_path, excludes):
                files[rel_path] = p
        return files

    def find_license_files(self, metadata: StandardMetadata) -> list[str]:
        result: list[str] = []
        if file := getattr(metadata.license, "file", None):
            result.append(file.relative_to(self.location).as_posix())
        if metadata.license_files:
            for file in metadata.license_files:
                result.append(file.as_posix())
        if (
            not result and metadata.license_files is None
        ):  # no license files specified, find from default patterns for backward compatibility
            for pattern in ["LICEN[CS]E*", "COPYING*", "NOTICE*"]:
                for path in self.location.glob(pattern):
                    if path.is_file():
                        result.append(path.relative_to(self.location).as_posix())
        return result

    def _get_include_and_exclude(self) -> tuple[set[str], set[str]]:
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
        return includes, excludes

    def _get_include_and_exclude_paths(self) -> tuple[list[str], list[str]]:
        includes, excludes = self._get_include_and_exclude()
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

    def _is_excluded(self, path: str, exclude_paths: Iterable[str]) -> bool:
        return any(
            is_same_or_descendant_path(path, exclude_path)
            or fnmatch(path, exclude_path)
            for exclude_path in exclude_paths
        )

    def _show_add_file(self, rel_path: str, full_path: Path) -> None:
        try:
            show_path = full_path.relative_to(self.location)
        except ValueError:
            show_path = full_path
        print(f" - Adding {show_path} -> {rel_path}")
