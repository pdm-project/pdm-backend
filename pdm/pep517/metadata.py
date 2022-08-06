from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, Mapping, TypeVar, cast

from pdm.pep517._vendor.packaging.requirements import Requirement
from pdm.pep517.exceptions import MetadataError, PDMWarning, ProjectError
from pdm.pep517.license import normalize_expression
from pdm.pep517.utils import (
    cd,
    ensure_pep440_req,
    find_packages_iter,
    merge_marker,
    safe_name,
    show_warning,
    to_filename,
)
from pdm.pep517.validator import validate_pep621
from pdm.pep517.version import DynamicVersion

T = TypeVar("T")


class MetaField(Generic[T]):
    def __init__(
        self, name: str, fget: Callable[[Metadata, Any], T] | None = None
    ) -> None:
        self.name = name
        self.fget = fget

    def __get__(self, instance: Metadata, owner: type[Metadata]) -> T | None:
        if instance is None:
            return self
        try:
            rv = instance.data[self.name]
        except KeyError:
            return None
        if self.fget is not None:
            rv = self.fget(instance, rv)
        return rv


class Metadata:
    """A class that holds all metadata that Python packaging requries."""

    DEFAULT_ENCODING = "utf-8"
    SUPPORTED_CONTENT_TYPES = ("text/markdown", "text/x-rst", "text/plain")

    def __init__(self, root: str | Path, pyproject: dict[str, Any]) -> None:
        self.root = Path(root).absolute()
        if "project" not in pyproject:
            raise ProjectError("No [project] config in pyproject.toml")
        self.data = pyproject["project"]
        self.config = Config(self.root, pyproject.get("tool", {}).get("pdm", {}))

    def validate(self, raising: bool = False) -> bool:
        return validate_pep621(self.data, raising)

    @property
    def name(self) -> str:
        if "name" not in self.data:
            raise MetadataError("name", "must be given in the project table")
        return self.data["name"]

    @property
    def version(self) -> str | None:
        static_version = self.data.get("version")
        if isinstance(static_version, str):
            return static_version
        if "version" in self.config.data and not (
            self.dynamic and "version" in self.dynamic
        ):
            raise MetadataError("version", "missing from 'dynamic' fields")
        dynamic_version = self.config.dynamic_version
        return (
            dynamic_version.evaluate_in_project(self.root) if dynamic_version else None
        )

    description: MetaField[str] = MetaField("description")

    def _get_readme_file(self, value: Mapping[str, str] | str) -> str:
        if isinstance(value, str):
            return value
        return value.get("file", "")

    def _get_readme_content(self, value: Mapping[str, str] | str) -> str:
        if isinstance(value, str):
            return Path(value).read_text(encoding=self.DEFAULT_ENCODING)
        if "file" in value and "text" in value:
            raise MetadataError(
                "readme",
                "readme table shouldn't specify both 'file' "
                "and 'text' at the same time",
            )
        if "text" in value:
            return value["text"]
        file_path = value.get("file", "")
        encoding = value.get("charset", self.DEFAULT_ENCODING)
        return Path(file_path).read_text(encoding=encoding)

    def _get_content_type(self, value: Mapping[str, str] | str) -> str:
        if isinstance(value, str):
            if value.lower().endswith(".md"):
                return "text/markdown"
            elif value.lower().endswith(".rst"):
                return "text/x-rst"
            return "text/plain"
        content_type = value.get("content-type")
        if not content_type:
            raise MetadataError(
                "readme", "'content-type' is missing in the readme table"
            )
        if content_type not in self.SUPPORTED_CONTENT_TYPES:
            raise MetadataError(
                "readme", f"Unsupported readme content-type: {content_type}"
            )
        return content_type

    readme: MetaField[str] = MetaField("readme", _get_readme_file)
    long_description: MetaField[str] = MetaField("readme", _get_readme_content)
    long_description_content_type: MetaField[str] = MetaField(
        "readme", _get_content_type
    )

    def _get_name(self, value: Iterable[Mapping[str, str]]) -> str:
        result = []
        for item in value:
            if "email" not in item and "name" in item:
                result.append(item["name"])
        return ",".join(result)

    def _get_email(self, value: Iterable[Mapping[str, str]]) -> str:
        result = []
        for item in value:
            if "email" not in item:
                continue
            email = (
                item["email"]
                if "name" not in item
                else "{name} <{email}>".format(**item)
            )
            result.append(email)
        return ",".join(result)

    author: MetaField[str] = MetaField("authors", _get_name)
    author_email: MetaField[str] = MetaField("authors", _get_email)
    maintainer: MetaField[str] = MetaField("maintainers", _get_name)
    maintainer_email: MetaField[str] = MetaField("maintainers", _get_email)

    @property
    def classifiers(self) -> list[str]:
        classifers = set(self.data.get("classifiers", []))

        if self.dynamic and "classifiers" in self.dynamic:
            show_warning(
                "`classifiers` no longer supports dynamic filling, "
                "please remove it from `dynamic` fields and manually "
                "supply all the classifiers",
                PDMWarning,
                stacklevel=2,
            )
        # if any(line.startswith("License :: ") for line in classifers):
        #     show_warning(
        #         "License classifiers are deprecated in favor of PEP 639 "
        #         "'license-expression' field.",
        #         PDMWarning,
        #         stacklevel=2,
        #     )

        return sorted(classifers)

    keywords: MetaField[str] = MetaField("keywords")
    project_urls: MetaField[dict[str, str]] = MetaField("urls")

    @property
    def license_expression(self) -> str | None:
        if "license-expression" in self.data:
            if "license" in self.data:
                raise MetadataError(
                    "license-expression",
                    "Can't specify both 'license' and 'license-expression' fields",
                )
            return normalize_expression(self.data["license-expression"])
        elif "license" in self.data and "text" in self.data["license"]:
            # show_warning(
            #     "'license' field is deprecated in favor of 'license-expression'",
            #     PDMWarning,
            #     stacklevel=2,
            # )
            # TODO: do not validate legacy license text,
            # remove this after PEP 639 is finalized
            return self.data["license"]["text"]
        elif "license-expression" not in (self.dynamic or []):
            show_warning("'license-expression' is missing", PDMWarning, stacklevel=2)
        return None

    @property
    def license_files(self) -> dict[str, list[str]]:
        if "license-files" not in self.data:
            if self.data.get("license", {}).get("file"):
                # show_warning(
                #     "'license.file' field is deprecated in favor of 'license-files'",
                #     PDMWarning,
                #     stacklevel=2,
                # )
                return {"paths": [self.data["license"]["file"]]}
            return {
                "globs": [
                    "LICENSES/*",
                    "LICEN[CS]E*",
                    "COPYING*",
                    "NOTICE*",
                    "AUTHORS*",
                ]
            }
        if "license" in self.data:
            raise MetadataError(
                "license-files",
                "Can't specify both 'license' and 'license-files' fields",
            )
        rv = self.data["license-files"]
        valid_keys = {"globs", "paths"} & set(rv)
        if len(valid_keys) == 2:
            raise MetadataError(
                "license-files", "Can't specify both 'paths' and 'globs'"
            )
        if not valid_keys:
            raise MetadataError("license-files", "Must specify 'paths' or 'globs'")
        return rv

    def _convert_dependencies(
        self, deps: list[str], field: str = "dependencies"
    ) -> list[str]:
        return list(filter(None, (ensure_pep440_req(dep, field) for dep in deps)))

    def _convert_optional_dependencies(
        self, deps: Mapping[str, list[str]]
    ) -> dict[str, list[str]]:
        return {
            k: self._convert_dependencies(deps[k], "optional-dependencies")
            for k in deps
        }

    dependencies: MetaField[list[str]] = MetaField(
        "dependencies", _convert_dependencies
    )
    optional_dependencies: MetaField[dict[str, list[str]]] = MetaField(
        "optional-dependencies", _convert_optional_dependencies
    )
    dynamic: MetaField[list[str]] = MetaField("dynamic")

    @property
    def project_name(self) -> str | None:
        if self.name is None:
            return None
        return safe_name(self.name)

    @property
    def project_filename(self) -> str:
        if self.project_name is None:
            return "UNKNOWN"
        return to_filename(self.project_name)

    @property
    def requires_extra(self) -> dict[str, list[str]]:
        """For PKG-INFO metadata"""
        if not self.optional_dependencies:
            return {}
        result: dict[str, list[str]] = {}
        for name, reqs in self.optional_dependencies.items():
            current = result[name] = []
            for r in reqs:
                parsed = Requirement(r)
                merge_marker(parsed, f"extra == {name!r}")
                current.append(str(parsed))
        return result

    @property
    def requires_python(self) -> str:
        result = self.data.get("requires-python", "")
        return "" if result == "*" else result

    @property
    def entry_points(self) -> dict[str, list[str]]:
        result = {}
        settings = self.data
        if "scripts" in settings:
            result["console_scripts"] = [
                f"{key} = {value}" for key, value in settings["scripts"].items()
            ]
        if "gui-scripts" in settings:
            result["gui_scripts"] = [
                f"{key} = {value}" for key, value in settings["gui-scripts"].items()
            ]
        if "entry-points" in settings:
            for plugin, value in settings["entry-points"].items():
                if plugin in ("console_scripts", "gui_scripts"):
                    correct_key = (
                        "scripts" if plugin == "console_scripts" else "gui-scripts"
                    )
                    raise MetadataError(
                        "entry-points",
                        f"entry-points {plugin!r} should be defined in "
                        f"[project.{correct_key}]",
                    )
                result[plugin] = [f"{k} = {v}" for k, v in value.items()]
        return result

    def convert_package_paths(self) -> dict[str, list | dict]:
        """Return a {package_dir, packages, package_data, exclude_package_data} dict."""
        packages = []
        py_modules = []
        package_data = {"": ["*"]}
        exclude_package_data: dict[str, list[str]] = {}
        package_dir = self.config.package_dir
        includes = self.config.includes
        excludes = self.config.excludes

        with cd(self.root.as_posix()):
            src_dir = Path(package_dir or ".")
            if not includes:
                packages = list(
                    find_packages_iter(
                        package_dir or ".",
                        exclude=["tests", "tests.*"],
                        src=str(src_dir),
                    )
                )
                if not packages:
                    py_modules = [path.name[:-3] for path in src_dir.glob("*.py")]
            else:
                packages_set = set()
                includes = includes[:]
                for include in includes[:]:
                    if include.replace("\\", "/").endswith("/*"):
                        include = include[:-2]
                    if "*" not in include and os.path.isdir(include):
                        dir_name = include.rstrip("/\\")
                        temp = list(
                            find_packages_iter(dir_name, src=package_dir or ".")
                        )
                        if os.path.isfile(os.path.join(dir_name, "__init__.py")):
                            temp.insert(0, dir_name)
                        packages_set.update(temp)
                        includes.remove(include)
                packages[:] = list(packages_set)
                for include in includes:
                    for path in glob.glob(include, recursive=True):
                        if "/" not in path.lstrip("./") and path.endswith(".py"):
                            # Only include top level py modules
                            py_modules.append(path.lstrip("./")[:-3])
                    if include.endswith(".py"):
                        continue
                    for package in packages:
                        relpath = os.path.relpath(include, package)
                        if not relpath.startswith(".."):
                            package_data.setdefault(package, []).append(relpath)
                for exclude in excludes:
                    for package in packages:
                        relpath = os.path.relpath(exclude, package)
                        if not relpath.startswith(".."):
                            exclude_package_data.setdefault(package, []).append(relpath)
            if packages and py_modules:
                raise ProjectError(
                    "Can't specify packages and py_modules at the same time."
                )
        return {
            "package_dir": {"": package_dir} if package_dir else {},
            "packages": packages,
            "py_modules": py_modules,
            "package_data": package_data,
            "exclude_package_data": exclude_package_data,
        }


class Config:
    """The [tool.pdm] table"""

    def __init__(self, root: Path, data: dict[str, Any]) -> None:
        self.root = root
        self.data = data

    def _compatible_get(
        self, name: str, default: Any = None, old_name: str | None = None
    ) -> Any:
        if name in self.data.get("build", {}):
            return self.data["build"][name]
        old_name = old_name or name
        if old_name in self.data:
            show_warning(
                f"Field `{old_name}` is renamed to `{name}` under [tool.pdm.build] "
                "table, please update your pyproject.toml accordingly",
                PDMWarning,
                stacklevel=2,
            )
            return self.data[old_name]
        return default

    @property
    def includes(self) -> list[str]:
        return self._compatible_get("includes", [])

    @property
    def source_includes(self) -> list[str]:
        return self._compatible_get("source-includes", [])

    @property
    def excludes(self) -> list[str]:
        return self._compatible_get("excludes", [])

    @property
    def setup_script(self) -> str | None:
        build_table = self.data.get("build", {})
        if "setup-script" in build_table:
            return build_table["setup-script"]
        if isinstance(build_table, str):
            show_warning(
                "Field `build` is renamed to `setup-script` under [tool.pdm.build] "
                "table, please update your pyproject.toml accordingly",
                PDMWarning,
                stacklevel=2,
            )
            return build_table
        return None

    @property
    def run_setuptools(self) -> bool:
        build = self.data.get("build", {})
        return isinstance(build, str) or cast(dict, build).get("run-setuptools", False)

    @property
    def package_dir(self) -> str:
        """A directory that will be used to looking for packages."""
        default = "src" if self.root.joinpath("src").exists() else ""
        return self._compatible_get("package-dir", default)

    @property
    def is_purelib(self) -> bool:
        """If not explicitly set, the project is considered to be non-pure
        if `build` exists.
        """
        return self._compatible_get("is-purelib", not bool(self.run_setuptools))

    @property
    def editable_backend(self) -> str:
        """Currently only two backends are supported:
        - editables: Proxy modules via editables
        - path: the legacy .pth file method(default)
        """
        return self._compatible_get("editable-backend", "path")

    @property
    def dynamic_version(self) -> DynamicVersion | None:
        dynamic_version = self.data.get("version")
        if not dynamic_version:
            return None
        return DynamicVersion.from_toml(dynamic_version)
