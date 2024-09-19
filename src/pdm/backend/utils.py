from __future__ import annotations

import ast
import contextlib
import functools
import importlib.util
import os
import re
import sys
import types
import urllib.parse
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Callable, Generator, Iterable, Match

from pdm.backend._vendor.packaging.markers import Marker
from pdm.backend._vendor.packaging.requirements import Requirement
from pdm.backend._vendor.packaging.version import InvalidVersion, Version
from pdm.backend.exceptions import ConfigError


def safe_version(version: str) -> str:
    """
    Convert an arbitrary string to a standard version string
    """
    try:
        # normalize the version
        return str(Version(version))
    except InvalidVersion:
        version = version.replace(" ", ".")
        return re.sub("[^A-Za-z0-9.]+", "-", version)


def to_filename(name: str) -> str:
    """Convert a project or version name to its filename-escaped form

    Any '-' characters are currently replaced with '_'.
    """
    return name.replace("-", "_")


def is_python_package(fullpath: str) -> bool:
    if not os.path.isdir(fullpath):
        return False
    if os.path.basename(fullpath.rstrip("/")) in ("__pycache__", "__pypackages__"):
        return False
    return os.path.isfile(os.path.join(fullpath, "__init__.py"))


def merge_marker(requirement: Requirement, marker: str) -> None:
    """Merge the target marker str with the requirement markers"""
    if not requirement.marker:
        requirement.marker = Marker(marker)
        return
    old_marker = requirement.marker
    if "or" in old_marker._markers:
        new_marker = Marker(f"({old_marker}) and {marker}")
    else:
        new_marker = Marker(f"{old_marker} and {marker}")
    requirement.marker = new_marker


def find_packages_iter(
    where: str = ".",
    exclude: Iterable[str] = (),
    include: Iterable[str] = ("*",),
    src: str = ".",
) -> Iterable[str]:
    """
    All the packages found in 'where' that pass the 'include' filter, but
    not the 'exclude' filter.
    """

    def _build_filter(patterns: Iterable[str]) -> Callable[[str], bool]:
        """
        Given a list of patterns, return a callable that will be true only if
        the input matches at least one of the patterns.
        """
        return lambda name: any(fnmatchcase(name, pat=pat) for pat in patterns)

    fexclude, finclude = _build_filter(exclude), _build_filter(include)
    for root, dirs, _files in os.walk(where, followlinks=True):
        # Copy dirs to iterate over it, then empty dirs.
        all_dirs = dirs[:]
        dirs[:] = []

        for dir in all_dirs:
            full_path = os.path.join(root, dir)
            rel_path = os.path.relpath(full_path, src)
            package = rel_path.replace(os.path.sep, ".")
            # Skip directory trees that are not valid packages
            if "." in dir:
                continue

            # Should this package be included?
            if (
                os.path.isfile(os.path.join(full_path, "__init__.py"))
                and finclude(package)
                and not fexclude(package)
            ):
                yield package

            # Keep searching subdirectories, as there may be more packages
            # down there, even if the parent was excluded.
            dirs.append(dir)


def normalize_path(filename: str | Path) -> str:
    """Normalize a file/dir name for comparison purposes"""
    filename = os.path.abspath(filename) if sys.platform == "cygwin" else filename
    return os.path.normcase(os.path.realpath(os.path.normpath(filename)))


def is_relative_path(target: Path, other: Path) -> bool:
    try:
        target.relative_to(other)
    except ValueError:
        return False
    else:
        return True


def expand_vars(line: str, root: str) -> str:
    """Expand environment variables in a string."""
    if "$" not in line:
        return line

    if "://" in line:
        quote: Callable[[str], str] = urllib.parse.quote
    else:
        quote = str
    line = line.replace("file:///${PROJECT_ROOT}", Path(root).as_uri())

    def replace_func(match: Match[str]) -> str:
        rv = os.getenv(match.group(1))
        if rv is None:
            return match.group(0)
        return quote(rv)

    return re.sub(r"\$\{(.+?)\}", replace_func, line)


def import_module_at_path(
    src_path: str | Path, module_name: str = "_local", context: Path | None = None
) -> types.ModuleType:
    """Import a module from a given path."""
    spec = importlib.util.spec_from_file_location(module_name, src_path)
    if spec is None:
        raise ValueError(f"Could not import module {module_name} from {src_path}")
    if context is not None:
        sys.path.insert(0, str(context.absolute()))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    if context is not None:
        sys.path.pop(0)
    return module


def normalize_file_permissions(st_mode: int) -> int:
    """
    Normalizes the permission bits in the st_mode field from stat to 644/755
    Popular VCSs only track whether a file is executable or not. The exact
    permissions can vary on systems with different umasks. Normalising
    to 644 (non executable) or 755 (executable) makes builds more reproducible.
    """
    # Set 644 permissions, leaving higher bits of st_mode unchanged
    new_mode = (st_mode | 0o644) & ~0o133
    if st_mode & 0o100:
        new_mode |= 0o111  # Executable: 644 -> 755

    return new_mode


@contextlib.contextmanager
def patch_sys_path(path: str | Path) -> Generator[None]:
    old_path = sys.path[:]
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path[:] = old_path


_attr_regex = re.compile(r"([\w.]+):([\w.]+)\s*(\([^)]+\))?")


def evaluate_module_attribute(
    expression: str, context: Path | None = None
) -> tuple[Any, tuple[Any, ...]]:
    """Evaluate the value of an expression like '<module>:<attribute>'

    Returns:
        the object and the calling arguments if any
    """
    if context is None:
        cm = contextlib.nullcontext()
    else:
        cm = patch_sys_path(context)  # type: ignore[assignment]

    matched = _attr_regex.match(expression)
    if matched is None:
        raise ConfigError(
            "Invalid expression, must be in the format of " "`module:attribute`."
        )
    with cm:
        module = importlib.import_module(matched.group(1))
        attrs = matched.group(2).split(".")
        obj: Any = functools.reduce(getattr, attrs, module)
        args_group = matched.group(3)
        if args_group:
            # make tuple
            args_group = args_group.strip()[:-1] + ",)"
            args = ast.literal_eval(args_group)

        else:
            args = ()
        return obj, args
