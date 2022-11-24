from __future__ import annotations

import abc
import glob
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Iterable, Mapping, TypeVar, cast

from pdm.backend.config import Config
from pdm.backend.exceptions import PDMWarning, ValidationError
from pdm.backend.hooks import BuildHookInterface, Context
from pdm.backend.utils import import_module_at_path, is_python_package

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


class Builder(metaclass=abc.ABC):
    """Base class for building and distributing a package from given path."""

    target: str
    DEFAULT_EXCLUDES = ["build"]

    def __init__(
        self,
        location: str | Path,
        config_settings: Mapping[str, Any] | None = None,
    ) -> None:
        self._old_cwd: str | None = None
        self.location = Path(location)
        self.config_settings = dict(config_settings or {})
        self._hooks = list(self._load_hooks())

    def _load_hooks(self) -> Iterable[BuildHookInterface]:
        """Load hooks in the following order:

        1. plugins installed in 'pdm.build.hook' entry point group.
        2. local hook defined in the `pdm_build.py` file.
        """
        for ep in entry_points(group="pdm.build.hook"):
            hook = ep.load()
            try:
                yield cast(BuildHookInterface, hook())  # for a hook class
            except TypeError:
                yield cast(BuildHookInterface, hook)  # for a hook module
        local_hook = self.location / "pdm_build.py"
        if local_hook.exists():
            yield cast(BuildHookInterface, import_module_at_path(local_hook))

    def call_hook(self, hook_name: str, *args: Any) -> None:
        """Call the hook on all registered hooks and skip if not implemented."""
        for hook in self._hooks:
            if hasattr(hook, hook_name):
                getattr(hook, hook_name)(*args)

    def build_context(self, destination: Path) -> Context:
        build_dir = self.location / "build"
        build_dir.mkdir(0o700, exist_ok=True)
        return Context(
            config=Config.from_pyproject(self.location),
            target=self.target,
            build_dir=build_dir,
            dist_dir=destination,
            config_settings=self.config_settings,
        )

    def __enter__(self: T) -> T:
        self._old_cwd = os.getcwd()
        os.chdir(self.location)
        return self

    def __exit__(self, *args: Any) -> None:
        assert self._old_cwd
        os.chdir(self._old_cwd)

    def initialize(self, context: Context) -> None:
        self.call_hook("initialize", context)

    def get_file_list(self, context: Context) -> Iterable[tuple[str, str]]:
        """Get the files to add to the package, return a iterable of
        (path: relpath).
        """
        files = self._find_files_to_add(context)
        self.call_hook("update_file_list", context, files)
        return sorted(files.items())

    def finalize(self, context: Context, artifact: Path) -> None:
        self.call_hook("finalize", context, artifact)

    def build(self, build_dir: str, **kwargs: Any) -> str:
        context = self.build_context(Path(build_dir))
        self.initialize(context)
        artifact = self.build_artifact(context, **kwargs)
        self.finalize(context, artifact)
        return artifact.name

    @abc.abstractmethod
    def build_artifact(self, context: Context, **kwargs: Any) -> Path:
        """Build the artifact and return the path to it."""

    def format_pkginfo(self, context: Context) -> str:
        metadata = context.config.as_standard_metadata()
        return str(metadata.as_rfc822())

    def _find_files_to_add(self, context: Context) -> dict[str, str]:
        """This is always the first hook, intialize the file list."""
        includes, excludes = self._get_include_and_exclude_paths(context)
        files: dict[str, str] = {}
        for include_path in includes:
            path = Path(include_path)
            if path.is_file():
                files[include_path] = include_path
                continue
            # The path is a directory name
            for p in path.glob("**/*"):
                if not p.is_file():
                    continue

                rel_path = p.absolute().relative_to(context.root).as_posix()
                if p.name.endswith(".pyc") or self._is_excluded(rel_path, excludes):
                    continue

                files[rel_path] = rel_path

        if context.target != "sdist":
            dist_info = getattr(context, "dist_info", "")
            for file in self.find_license_files(context):
                files[file] = f"{dist_info}/licenses/{file}"
            return files

        if context.config.backend_config.setup_script and os.path.isfile(
            context.config.backend_config.setup_script
        ):
            setup_script = context.config.backend_config.setup_script
            files[setup_script] = setup_script

        readme_file = context.config.metadata.readme_file
        if readme_file and (context.root / readme_file).exists():
            files[readme_file] = readme_file

        # The pyproject.toml file is valid at this point, include it
        files["pyproject.toml"] = "pyproject.toml"
        for file in self.find_license_files(context):
            files[file] = file
        return files

    def find_license_files(self, context: Context) -> list[str]:
        """Return a list of license files from the PEP 639 metadata."""
        root = context.root
        license_files = context.config.metadata.license_files
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

    def _get_include_and_exclude_paths(
        self, context: Context
    ) -> tuple[list[str], list[str]]:
        includes = set()
        excludes = set(self.DEFAULT_EXCLUDES)
        build_config = context.config.backend_config
        meta_excludes = list(build_config.excludes)
        source_includes = build_config.source_includes or ["tests"]
        if context.target != "sdist":
            # exclude source-includes for non-sdist builds
            meta_excludes.extend(source_includes)

        if not build_config.includes:
            top_packages = _find_top_packages(build_config.package_dir or ".")
            if top_packages:
                includes.update(top_packages)
            else:
                includes.add(f"{build_config.package_dir or '.'}/*.py")
        else:
            includes.update(build_config.includes)

        includes.update(source_includes)
        excludes.update(meta_excludes)

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
