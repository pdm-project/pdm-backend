import atexit
import glob
import os
import textwrap
import warnings
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple, TypeVar, Union

from pdm.pep517.exceptions import MetadataError, PDMWarning
from pdm.pep517.metadata import Metadata
from pdm.pep517.utils import is_python_package, safe_version, to_filename

OPEN_README = """import codecs

with codecs.open({readme!r}, encoding="utf-8") as fp:
    long_description = fp.read()
"""

SETUP_FORMAT = """
# -*- coding: utf-8 -*-
from setuptools import setup

{before}
setup_kwargs = {{
    'name': {name!r},
    'version': {version!r},
    'description': {description!r},
    'long_description': long_description,
    'license': {license!r},
    'author': {author!r},
    'author_email': {author_email!r},
    'maintainer': {maintainer!r},
    'maintainer_email': {maintainer_email!r},
    'url': {url!r},
{extra}
}}
{after}

setup(**setup_kwargs)
"""

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
    include_globs: Dict[str, str], excludes_globs: Dict[str, str]
) -> Tuple[List[str], List[str]]:
    """Correctly merge includes and excludes.
    When a pattern exists in both includes and excludes,
    determine the priority in the following ways:

    1. The one with more parts in the path wins
    2. If part numbers are equal, the one that is more concrete wins
    3. If both have the same part number and concrete level, *excludes* wins
    """

    def path_weight(pathname: str) -> Tuple[int, int]:
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


def _find_top_packages(root: str) -> List[str]:
    result = []
    for path in os.listdir(root):
        path = os.path.join(root, path)
        if is_python_package(path):
            result.append(path)
    return result


def _format_list(data: List[str], indent: int = 4) -> str:
    result = ["["]
    for row in data:
        result.append(" " * indent + repr(row) + ",")
    result.append(" " * (indent - 4) + "]")
    return "\n".join(result)


def _format_dict_list(data: Dict[str, List[str]], indent: int = 4) -> str:
    result = ["{"]
    for key, value in data.items():
        result.append(
            " " * indent + repr(key) + ": " + _format_list(value, indent + 4) + ","
        )
    result.append(" " * (indent - 4) + "}")
    return "\n".join(result)


class Builder:
    """Base class for building and distributing a package from given path."""

    DEFAULT_EXCLUDES = ["build"]

    def __init__(
        self,
        location: Union[str, Path],
        config_settings: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._old_cwd: Optional[str] = None
        self.location = Path(location).absolute()
        self.config_settings = config_settings
        self._meta: Optional[Metadata] = None

    @property
    def meta(self) -> Metadata:
        if not self._meta:
            self._meta = Metadata(self.location / "pyproject.toml")
            self._meta.validate(True)
        return self._meta

    @property
    def meta_version(self) -> str:
        meta_version = self.meta.version
        if meta_version is None:
            return "0.0.0"
        return to_filename(safe_version(meta_version))

    def __enter__(self: T) -> T:
        self._old_cwd = os.getcwd()
        os.chdir(self.location)
        return self

    def __exit__(self, *args: Any) -> None:
        assert self._old_cwd
        os.chdir(self._old_cwd)

    def build(self, build_dir: str, **kwargs: Any) -> str:
        raise NotImplementedError

    def _get_include_and_exclude_paths(
        self, for_sdist: bool = False
    ) -> Tuple[List[str], List[str]]:
        includes = set()
        excludes = set(self.DEFAULT_EXCLUDES)

        meta_excludes = list(self.meta.excludes)
        source_includes = self.meta.source_includes or ["tests"]
        if not for_sdist:
            # exclude source-includes for non-sdist builds
            meta_excludes.extend(source_includes)

        if not self.meta.includes:
            top_packages = _find_top_packages(self.meta.package_dir or ".")
            if top_packages:
                includes.update(top_packages)
            else:
                includes.add(f"{self.meta.package_dir or '.'}/*.py")
        else:
            includes.update(self.meta.includes)

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

    def _is_excluded(self, path: str, exclude_paths: List[str]) -> bool:
        return any(
            is_same_or_descendant_path(path, exclude_path)
            for exclude_path in exclude_paths
        )

    def _find_files_iter(self, for_sdist: bool = False) -> Iterator[str]:
        includes, excludes = self._get_include_and_exclude_paths(for_sdist)
        for include_path in includes:
            path = Path(include_path)
            if path.is_file():
                yield include_path
                continue
            # The path is a directory name
            for p in path.glob("**/*"):
                if not p.is_file():
                    continue

                rel_path = p.absolute().relative_to(self.location).as_posix()
                if p.name.endswith(".pyc") or self._is_excluded(rel_path, excludes):
                    continue

                yield rel_path

        if not for_sdist:
            return

        if self.meta.build and os.path.isfile(self.meta.build):
            yield self.meta.build

        if self.meta.readme and os.path.isfile(self.meta.readme):
            yield self.meta.readme

        if self.meta.filepath.exists():
            yield self.meta.filepath.name

    def find_files_to_add(self, for_sdist: bool = False) -> List[Path]:
        """Traverse the project path and return a list of file names
        that should be included in a sdist distribution.
        If for_sdist is True, will include files like LICENSE, README and pyproject
        Produce a paths list relative to the source dir.
        """
        return sorted({Path(p) for p in self._find_files_iter(for_sdist)})

    def find_license_files(self) -> List[str]:
        """Return a list of license files from the PEP 639 metadata."""
        license_files = self.meta.license_files
        if "paths" in license_files:
            invalid_paths = [
                p for p in license_files["paths"] if not (self.location / p).is_file()
            ]
            if invalid_paths:
                raise MetadataError(
                    "license-files", f"License files not found: {invalid_paths}"
                )
            return license_files["paths"]
        else:
            paths = [
                p.relative_to(self.location).as_posix()
                for pattern in license_files["globs"]
                for p in self.location.glob(pattern)
            ]
            if license_files["globs"] and not paths:
                warnings.warn(
                    f"No license files are matched with glob patterns "
                    f"{license_files['globs']}.",
                    PDMWarning,
                    stacklevel=2,
                )
            return paths

    def format_setup_py(self) -> str:
        before, extra, after = [], [], []
        meta = self.meta
        kwargs = {
            "name": meta.name,
            "version": meta.version,
            "author": meta.author,
            "license": meta.license_expression,
            "author_email": meta.author_email,
            "maintainer": meta.maintainer,
            "maintainer_email": meta.maintainer_email,
            "description": meta.description,
            "url": (meta.project_urls or {}).get("homepage", ""),
        }

        if meta.build:
            # The build script must contain a `build(setup_kwargs)`, we just import
            # and execute it.
            after.extend(
                [
                    "from {} import build\n".format(meta.build.split(".")[0]),
                    "build(setup_kwargs)\n",
                ]
            )

        package_paths = meta.convert_package_paths()
        if package_paths["packages"]:
            extra.append(
                "    'packages': {},\n".format(
                    _format_list(package_paths["packages"], 8)
                )
            )
        if package_paths["package_dir"]:
            extra.append(
                "    'package_dir': {!r},\n".format(package_paths["package_dir"])
            )
        if package_paths["package_data"]:
            extra.append(
                "    'package_data': {!r},\n".format(package_paths["package_data"])
            )
        if package_paths["exclude_package_data"]:
            extra.append(
                "    'exclude_package_data': {!r},\n".format(
                    package_paths["exclude_package_data"]
                )
            )
        if meta.readme:
            before.append(OPEN_README.format(readme=meta.readme))
        elif meta.long_description:
            before.append(
                "long_description = '''{}'''\n".format(
                    repr(meta.long_description)[1:-1]
                )
            )
        else:
            before.append("long_description = None\n")
        if meta.long_description_content_type:
            extra.append(
                "    'long_description_content_type': {!r},\n".format(
                    meta.long_description_content_type
                )
            )

        if meta.keywords:
            extra.append(f"    'keywords': {meta.keywords!r},\n")
        if meta.classifiers:
            extra.append(f"    'classifiers': {_format_list(meta.classifiers, 8)},\n")
        if meta.dependencies:
            before.append(f"INSTALL_REQUIRES = {_format_list(meta.dependencies)}\n")
            extra.append("    'install_requires': INSTALL_REQUIRES,\n")
        if meta.optional_dependencies:
            before.append(
                "EXTRAS_REQUIRE = {}\n".format(
                    _format_dict_list(meta.optional_dependencies)
                )
            )
            extra.append("    'extras_require': EXTRAS_REQUIRE,\n")
        if meta.requires_python:
            extra.append(f"    'python_requires': {meta.requires_python!r},\n")
        if meta.entry_points:
            before.append(f"ENTRY_POINTS = {_format_dict_list(meta.entry_points)}\n")
            extra.append("    'entry_points': ENTRY_POINTS,\n")
        return SETUP_FORMAT.format(
            before="".join(before), after="".join(after), extra="".join(extra), **kwargs
        )

    def format_pkginfo(self, full: bool = True) -> str:
        meta = self.meta

        content = METADATA_BASE.format(name=meta.name, version=meta.version or "0.0.0")

        if meta.description:
            content += f"Summary: {meta.description}\n"

        if meta.license_expression:
            content += f"License: {meta.license_expression}\n"

        # Optional fields
        # TODO: enable this after twine supports metadata version 2.3
        # for license_file in self.find_license_files():
        #     content += f"License-File: {license_file}\n"

        if meta.keywords:
            content += "Keywords: {}\n".format(",".join(meta.keywords))

        if meta.author:
            content += f"Author: {meta.author}\n"

        if meta.author_email:
            content += f"Author-email: {meta.author_email}\n"

        if meta.maintainer:
            content += f"Maintainer: {meta.maintainer}\n"

        if meta.maintainer_email:
            content += f"Maintainer-email: {meta.maintainer_email}\n"

        if meta.requires_python:
            content += f"Requires-Python: {meta.requires_python}\n"

        for classifier in meta.classifiers or []:
            content += f"Classifier: {classifier}\n"

        if full:
            for dep in sorted(meta.dependencies or []):
                content += f"Requires-Dist: {dep}\n"

        for extra, reqs in sorted(meta.requires_extra.items()):
            content += f"Provides-Extra: {extra}\n"
            if full:
                for dep in reqs:
                    content += f"Requires-Dist: {dep}\n"

        for url in sorted(meta.project_urls or {}):
            content += f"Project-URL: {url}, {meta.project_urls[url]}\n"

        if meta.long_description_content_type:
            content += "Description-Content-Type: {}\n".format(
                meta.long_description_content_type
            )
        if meta.long_description:
            readme = meta.long_description
            if full:
                content += "\n" + readme + "\n"
            else:
                content += "Description: {}\n".format(
                    textwrap.indent(readme, " " * 8, lambda line: True).lstrip()
                )

        return content

    def ensure_setup_py(self, clean: bool = True) -> Path:
        """Ensures the requirement has a setup.py ready."""
        # XXX: Currently only handle PDM project, and do nothing if not.

        setup_py_path = self.location.joinpath("setup.py")
        if setup_py_path.is_file():
            return setup_py_path

        setup_py_path.write_text(self.format_setup_py(), encoding="utf-8")

        # Clean this temp file when process exits
        def cleanup() -> None:
            try:
                setup_py_path.unlink()
            except OSError:
                pass

        if clean:
            atexit.register(cleanup)
        return setup_py_path
