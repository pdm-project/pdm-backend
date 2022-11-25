from __future__ import annotations

import importlib.util
import os
import re
import sys
import sysconfig
import types
import urllib.parse
import warnings
from contextlib import contextmanager
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Callable, Generator, Iterable, Match

from pdm.backend._vendor.packaging import tags
from pdm.backend._vendor.packaging.markers import Marker
from pdm.backend._vendor.packaging.requirements import Requirement
from pdm.backend._vendor.packaging.version import InvalidVersion, Version
from pdm.backend.macosx_platform import calculate_macosx_platform_tag


def safe_name(name: str) -> str:
    """Convert an arbitrary string to a standard distribution name

    Any runs of non-alphanumeric/. characters are replaced with a single '-'.
    """
    return re.sub("[^A-Za-z0-9.]+", "-", name)


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


@contextmanager
def cd(path: str) -> Generator[None, None, None]:
    _old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(_old_cwd)


def normalize_path(filename: str | Path) -> str:
    """Normalize a file/dir name for comparison purposes"""
    filename = os.path.abspath(filename) if sys.platform == "cygwin" else filename
    return os.path.normcase(os.path.realpath(os.path.normpath(filename)))


def get_platform(build_dir: str | Path) -> str:
    """Return our platform name 'win32', 'linux_x86_64'"""
    result = sysconfig.get_platform()
    if result.startswith("macosx") and os.path.exists(build_dir):
        result = calculate_macosx_platform_tag(build_dir, result)
    if result in ("linux_x86_64", "linux-x86_64") and sys.maxsize == 2147483647:
        # pip pull request #3497
        result = "linux_i686"
    return result


def get_flag(
    var: str, fallback: bool, expected: bool = True, warn: bool = True
) -> bool:
    """Use a fallback value for determining SOABI flags if the needed config
    var is unset or unavailable."""
    val = sysconfig.get_config_var(var)
    if val is None:
        if warn:
            warnings.warn(
                "Config variable '{}' is unset, Python ABI tag may "
                "be incorrect".format(var),
                RuntimeWarning,
                2,
            )
        return fallback
    return val == expected


def get_abi_tag() -> str | None:
    """Return the ABI tag based on SOABI (if available) or emulate SOABI
    (CPython 2, PyPy)."""
    soabi = sysconfig.get_config_var("SOABI")
    impl = tags.interpreter_name()
    is_cpython = impl == "cp"
    if not soabi and impl in ("cp", "pp") and hasattr(sys, "maxunicode"):
        d = ""
        m = ""
        u = ""
        if get_flag("Py_DEBUG", hasattr(sys, "gettotalrefcount"), warn=is_cpython):
            d = "d"
        if sys.version_info < (3, 8) and get_flag(
            "WITH_PYMALLOC", is_cpython, warn=is_cpython
        ):
            m = "m"
        if sys.version_info < (3, 3) and get_flag(
            "Py_UNICODE_SIZE", sys.maxunicode == 0x10FFFF, expected=4, warn=is_cpython
        ):
            u = "u"
        return f"{impl}{tags.interpreter_version()}{d}{m}{u}"
    elif soabi and soabi.startswith("cpython-"):
        return "cp" + soabi.split("-")[1]
    elif soabi:
        return soabi.replace(".", "_").replace("-", "_")
    else:
        return None


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
    line = line.replace("${PROJECT_ROOT}", root.lstrip("/"))

    def replace_func(match: Match[str]) -> str:
        rv = os.getenv(match.group(1))
        if rv is None:
            return match.group(0)
        return urllib.parse.quote(rv)

    return re.sub(r"\$\{(.+?)\}", replace_func, line)


def import_module_at_path(
    src_path: str | Path, module_name: str = "_local"
) -> types.ModuleType:
    """Import a module from a given path."""
    spec = importlib.util.spec_from_file_location(module_name, src_path)
    if spec is None:
        raise ValueError(f"Could not import module {module_name} from {src_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module
