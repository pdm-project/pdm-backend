import atexit
import glob
import os
import textwrap
from pathlib import Path
from typing import Dict, Iterator, List, Tuple, Union

from .metadata import Metadata
from .utils import is_python_package, normalize_path

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
Summary: {description}
Home-page: {homepage}
License: {license}
"""


class BuildError(RuntimeError):
    pass


def _match_path(path: str, pattern: str) -> bool:
    return normalize_path(path) == normalize_path(pattern)


def _merge_globs(
    include_globs: Dict[str, str], excludes_globs: Dict[str, str]
) -> Tuple[List[str], List[str]]:
    includes, excludes = [], []
    for path, key in include_globs.items():
        # The longer glob pattern wins
        if path in excludes_globs:
            if len(key) <= excludes_globs[path]:
                continue
            else:
                del excludes_globs[path]
        includes.append(path)
    excludes = list(excludes_globs)
    return includes, excludes


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

    DEFAULT_EXCLUDES = ["ez_setup", "*__pycache__", "tests", "tests.*"]

    def __init__(self, location: Union[str, Path]) -> None:
        self._old_cwd = None
        self.location = Path(location).absolute()
        self._meta = None

    @property
    def meta(self) -> Metadata:
        if not self._meta:
            self._meta = Metadata(self.location / "pyproject.toml")
        return self._meta

    def __enter__(self) -> "Builder":
        self._old_cwd = os.getcwd()
        os.chdir(self.location)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        os.chdir(self._old_cwd)

    def build(self, build_dir: str, **kwargs) -> str:
        raise NotImplementedError

    def _find_files_iter(self, include_build: bool = False) -> Iterator[str]:
        includes = []
        find_froms = []
        excludes = []
        dont_find_froms = []

        if not self.meta.includes:
            find_froms = _find_top_packages(self.meta.package_dir or ".")
            if not find_froms:
                includes = ["*.py"]
        else:
            for pat in self.meta.includes:
                if os.path.basename(pat) == "*":
                    pat = pat[:-2]
                if "*" in pat or os.path.isfile(pat):
                    includes.append(pat)
                else:
                    find_froms.append(pat)

        if self.meta.excludes:
            for pat in self.meta.excludes:
                if "*" in pat or os.path.isfile(pat):
                    excludes.append(pat)
                else:
                    dont_find_froms.append(pat)

        include_globs = {path: key for key in includes for path in glob.glob(key)}
        excludes_globs = {path: key for key in excludes for path in glob.glob(key)}

        includes, excludes = _merge_globs(include_globs, excludes_globs)
        for path in find_froms:
            path_base = os.path.dirname(path)
            if not path_base or path_base == ".":
                # the path is top level itself
                path_base = path

            for root, dirs, filenames in os.walk(path):
                if root == "__pycache__" or any(
                    _match_path(root, item) for item in dont_find_froms
                ):
                    continue

                for filename in filenames:
                    if filename.endswith(".pyc") or any(
                        _match_path(os.path.join(root, filename), item)
                        for item in excludes
                    ):
                        continue
                    yield os.path.join(root, filename)

        for path in includes:
            if os.path.isfile(path):
                yield path
        if not include_build:
            return

        if self.meta.build and os.path.isfile(self.meta.build):
            yield self.meta.build

        for pat in ("COPYING", "LICENSE"):
            for path in glob.glob(pat + "*"):
                if os.path.isfile(path):
                    yield path

        if self.meta.readme and os.path.isfile(self.meta.readme):
            yield self.meta.readme

        if self.meta.filepath.exists():
            yield "pyproject.toml"

    def find_files_to_add(self, include_build: bool = False) -> List[Path]:
        """Traverse the project path and return a list of file names
        that should be included in a sdist distribution.
        If include_build is True, will include files like LICENSE, README and pyproject
        Produce a paths list relative to the source dir.
        """
        return sorted(set(Path(p) for p in self._find_files_iter(include_build)))

    def format_setup_py(self) -> str:
        before, extra, after = [], [], []
        meta = self.meta
        kwargs = {
            "name": meta.name,
            "version": meta.version,
            "author": meta.author,
            "license": meta.license_type,
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
            extra.append("    'keywords': {!r},\n".format(meta.keywords))
        if meta.classifiers:
            extra.append(
                "    'classifiers': {},\n".format(_format_list(meta.classifiers, 8))
            )
        if meta.dependencies:
            before.append(
                "INSTALL_REQUIRES = {}\n".format(_format_list(meta.dependencies))
            )
            extra.append("    'install_requires': INSTALL_REQUIRES,\n")
        if meta.optional_dependencies:
            before.append(
                "EXTRAS_REQUIRE = {}\n".format(
                    _format_dict_list(meta.optional_dependencies)
                )
            )
            extra.append("    'extras_require': EXTRAS_REQUIRE,\n")
        if meta.requires_python:
            extra.append("    'python_requires': {!r},\n".format(meta.requires_python))
        if meta.entry_points:
            before.append(
                "ENTRY_POINTS = {}\n".format(_format_dict_list(meta.entry_points))
            )
            extra.append("    'entry_points': ENTRY_POINTS,\n")
        return SETUP_FORMAT.format(
            before="".join(before), after="".join(after), extra="".join(extra), **kwargs
        )

    def format_pkginfo(self, full=True) -> str:
        meta = self.meta
        content = METADATA_BASE.format(
            name=meta.name or "UNKNOWN",
            version=meta.version or "UNKNOWN",
            homepage=meta.project_urls.get("homepage", "UNKNOWN")
            if meta.project_urls
            else "UNKNOWN",
            license=meta.license_type or "UNKNOWN",
            description=meta.description or "UNKNOWN",
            readme=(Path(meta.readme).read_text("utf-8") if meta.readme else "UNKNOWN"),
        )

        # Optional fields
        if meta.keywords:
            content += "Keywords: {}\n".format(",".join(meta.keywords))

        if meta.author:
            content += "Author: {}\n".format(meta.author)

        if meta.author_email:
            content += "Author-email: {}\n".format(meta.author_email)

        if meta.maintainer:
            content += "Maintainer: {}\n".format(meta.maintainer)

        if meta.maintainer_email:
            content += "Maintainer-email: {}\n".format(meta.maintainer_email)

        if meta.requires_python:
            content += "Requires-Python: {}\n".format(meta.requires_python)

        for classifier in meta.classifiers or []:
            content += "Classifier: {}\n".format(classifier)

        if full:
            for dep in sorted(meta.dependencies):
                content += "Requires-Dist: {}\n".format(dep)

        for extra, reqs in sorted(meta.requires_extra.items()):
            content += "Provides-Extra: {}\n".format(extra)
            if full:
                for dep in reqs:
                    content += "Requires-Dist: {}\n".format(dep)

        for url in sorted(meta.project_urls or {}):
            content += "Project-URL: {}, {}\n".format(url, meta.project_urls[url])

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
                    textwrap.indent(readme, " " * 8).lstrip()
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
        def cleanup():
            setup_py_path.unlink()

        if clean:
            atexit.register(cleanup)
        return setup_py_path
