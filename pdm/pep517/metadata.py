import glob
import os
import re
import warnings
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
)

from pdm.pep517._vendor import tomli
from pdm.pep517._vendor.packaging.requirements import Requirement
from pdm.pep517.exceptions import MetadataError, PDMWarning, ProjectError
from pdm.pep517.license import normalize_expression
from pdm.pep517.scm import get_version_from_scm
from pdm.pep517.utils import (
    cd,
    ensure_pep440_req,
    find_packages_iter,
    merge_marker,
    safe_name,
    to_filename,
)
from pdm.pep517.validator import validate_pep621

T = TypeVar("T")


class MetaField(Generic[T]):
    def __init__(
        self, name: str, fget: Optional[Callable[["Metadata", Any], T]] = None
    ) -> None:
        self.name = name
        self.fget = fget

    def __get__(self, instance: "Metadata", owner: Type["Metadata"]) -> Optional[T]:
        if instance is None:
            return self
        try:
            rv = instance._metadata[self.name]
        except KeyError:
            return None
        if self.fget is not None:
            rv = self.fget(instance, rv)
        return rv


class Metadata:
    """A class that holds all metadata that Python packaging requries."""

    DEFAULT_ENCODING = "utf-8"
    SUPPORTED_CONTENT_TYPES = ("text/markdown", "text/x-rst", "text/plain")

    def __init__(self, filepath: Union[str, Path], parse: bool = True) -> None:
        self.filepath = Path(filepath).absolute()
        self._tool_settings: Dict[str, Any] = {}
        self._metadata: Dict[str, Any] = {}
        if parse:
            self._read_pyproject()

    def _read_pyproject(self) -> None:
        try:
            with self.filepath.open("rb") as f:
                data = tomli.load(f)
        except FileNotFoundError:
            raise ProjectError("pyproject.toml does not exist.")
        except tomli.TOMLDecodeError:
            raise ProjectError("The project's pyproject.toml is not valid.")
        else:
            if "tool" in data and "pdm" in data["tool"]:
                self._tool_settings = data["tool"]["pdm"]
            if "project" in data:
                self._metadata = data["project"]
            else:
                raise ProjectError("No [project] config in pyproject.toml")

    def validate(self, raising: bool = False) -> bool:
        return validate_pep621(self._metadata, raising)

    @property
    def name(self) -> str:
        if "name" not in self._metadata:
            raise MetadataError("name", "must be given in the project table")
        return self._metadata["name"]

    @property
    def version(self) -> Optional[str]:
        static_version = self._metadata.get("version")
        if isinstance(static_version, str):
            return static_version
        dynamic_version = self._tool_settings.get("version")
        if isinstance(static_version, dict):
            warnings.warn(
                "`version` in [project] no longer supports dynamic filling. "
                "Move it to [tool.pdm] or change it to static string.\n"
                "It will raise an error in the next minor release.",
                PDMWarning,
                stacklevel=2,
            )
            if not dynamic_version:
                dynamic_version = static_version

        if not dynamic_version:
            return None
        if not self.dynamic or "version" not in self.dynamic:
            raise MetadataError("version", "missing from 'dynamic' fields")
        version_source = dynamic_version.get("from")
        if version_source:
            with self.filepath.parent.joinpath(version_source).open(
                encoding="utf-8"
            ) as fp:
                match = re.search(
                    r"^__version__\s*=\s*[\"'](.+?)[\"']\s*(?:#.*)?$", fp.read(), re.M
                )
                if not match:
                    raise MetadataError(
                        "version",
                        f"Can't find version in file {version_source}, "
                        "it should appear as `__version__ = 'a.b.c'`.",
                    )
                return match.group(1)
        elif dynamic_version.get("use_scm", False):
            return get_version_from_scm(self.filepath.parent)
        else:
            return None

    description: MetaField[str] = MetaField("description")

    def _get_readme_file(self, value: Union[Mapping[str, str], str]) -> str:
        if isinstance(value, str):
            return value
        return value.get("file", "")

    def _get_readme_content(self, value: Union[Mapping[str, str], str]) -> str:
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

    def _get_content_type(self, value: Union[Mapping[str, str], str]) -> str:
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
    def classifiers(self) -> List[str]:
        classifers = set(self._metadata.get("classifiers", []))

        if self.dynamic and "classifiers" in self.dynamic:
            warnings.warn(
                "`classifiers` no longer supports dynamic filling, "
                "please remove it from `dynamic` fields and manually "
                "supply all the classifiers",
                PDMWarning,
                stacklevel=2,
            )
        if any(line.startswith("License :: ") for line in classifers):
            warnings.warn(
                "License classifiers are deprecated in favor of PEP 639 "
                "'license-expression' field.",
                PDMWarning,
                stacklevel=2,
            )

        return sorted(classifers)

    keywords: MetaField[str] = MetaField("keywords")
    project_urls: MetaField[Dict[str, str]] = MetaField("urls")

    @property
    def license_expression(self) -> Optional[str]:
        if "license-expression" in self._metadata:
            if "license" in self._metadata:
                raise MetadataError(
                    "license-expression",
                    "Can't specify both 'license' and 'license-expression' fields",
                )
            return normalize_expression(self._metadata["license-expression"])
        elif "license" in self._metadata and "text" in self._metadata["license"]:
            # warnings.warn(
            #     "'license' field is deprecated in favor of 'license-expression'",
            #     PDMWarning,
            #     stacklevel=2,
            # )
            # TODO: do not validate legacy license text,
            # remove this after PEP 639 is finalized
            return self._metadata["license"]["text"]
        elif "license-expression" not in (self.dynamic or []):
            warnings.warn("'license-expression' is missing", PDMWarning, stacklevel=2)
        return None

    @property
    def license_files(self) -> Dict[str, List[str]]:
        if "license-files" not in self._metadata:
            if self._metadata.get("license", {}).get("file"):
                # warnings.warn(
                #     "'license.file' field is deprecated in favor of 'license-files'",
                #     PDMWarning,
                #     stacklevel=2,
                # )
                return {"paths": [self._metadata["license"]["file"]]}
            return {"globs": ["LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*"]}
        if "license" in self._metadata:
            raise MetadataError(
                "license-files",
                "Can't specify both 'license' and 'license-files' fields",
            )
        rv = self._metadata["license-files"]
        valid_keys = {"globs", "paths"} & set(rv)
        if len(valid_keys) == 2:
            raise MetadataError(
                "license-files", "Can't specify both 'paths' and 'globs'"
            )
        if not valid_keys:
            raise MetadataError("license-files", "Must specify 'paths' or 'globs'")
        return rv

    @property
    def includes(self) -> List[str]:
        return self._tool_settings.get("includes", [])

    @property
    def source_includes(self) -> List[str]:
        return self._tool_settings.get("source-includes", [])

    @property
    def excludes(self) -> List[str]:
        return self._tool_settings.get("excludes", [])

    @property
    def build(self) -> Optional[str]:
        return self._tool_settings.get("build")

    @property
    def package_dir(self) -> str:
        """A directory that will be used to looking for packages."""
        if "package-dir" in self._tool_settings:
            return self._tool_settings["package-dir"]
        elif self.filepath.parent.joinpath("src").is_dir():
            return "src"
        return ""

    @property
    def editable_backend(self) -> str:
        """Currently only two backends are supported:
        - editables: Proxy modules via editables
        - path: the legacy .pth file method(default)
        """
        return self._tool_settings.get("editable-backend", "path")

    def _convert_dependencies(self, deps: List[str]) -> List[str]:
        return list(filter(None, map(ensure_pep440_req, deps)))

    def _convert_optional_dependencies(
        self, deps: Mapping[str, List[str]]
    ) -> Dict[str, List[str]]:
        return {k: self._convert_dependencies(deps[k]) for k in deps}

    dependencies: MetaField[List[str]] = MetaField(
        "dependencies", _convert_dependencies
    )
    optional_dependencies: MetaField[Dict[str, List[str]]] = MetaField(
        "optional-dependencies", _convert_optional_dependencies
    )
    dynamic: MetaField[List[str]] = MetaField("dynamic")

    @property
    def project_name(self) -> Optional[str]:
        if self.name is None:
            return None
        return safe_name(self.name)

    @property
    def is_purelib(self) -> bool:
        """If not explicitly set, the project is considered to be non-pure
        if `build` exists.
        """
        if "is-purelib" in self._tool_settings:
            return self._tool_settings["is-purelib"]
        return self.build is None

    @property
    def project_filename(self) -> str:
        if self.name is None:
            return "UNKNOWN"
        return to_filename(self.project_name)

    @property
    def requires_extra(self) -> Dict[str, List[str]]:
        """For PKG-INFO metadata"""
        if not self.optional_dependencies:
            return {}
        result: Dict[str, List[str]] = {}
        for name, reqs in self.optional_dependencies.items():
            current = result[name] = []
            for r in reqs:
                parsed = Requirement(r)
                merge_marker(parsed, f"extra == {name!r}")
                current.append(str(parsed))
        return result

    @property
    def requires_python(self) -> str:
        result = self._metadata.get("requires-python", "")
        return "" if result == "*" else result

    @property
    def entry_points(self) -> Dict[str, List[str]]:
        result = {}
        settings = self._metadata
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

    def convert_package_paths(self) -> Dict[str, Union[List, Dict]]:
        """Return a {package_dir, packages, package_data, exclude_package_data} dict."""
        packages = []
        py_modules = []
        package_data = {"": ["*"]}
        exclude_package_data: Dict[str, List[str]] = {}

        with cd(self.filepath.parent.as_posix()):
            src_dir = Path(self.package_dir or ".")
            if not self.includes:
                packages = list(
                    find_packages_iter(
                        self.package_dir or ".",
                        exclude=["tests", "tests.*"],
                        src=src_dir,
                    )
                )
                if not packages:
                    py_modules = [path.name[:-3] for path in src_dir.glob("*.py")]
            else:
                packages_set = set()
                includes = self.includes[:]
                for include in includes[:]:
                    if include.replace("\\", "/").endswith("/*"):
                        include = include[:-2]
                    if "*" not in include and os.path.isdir(include):
                        dir_name = include.rstrip("/\\")
                        temp = list(
                            find_packages_iter(dir_name, src=self.package_dir or ".")
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
                for exclude in self.excludes or []:
                    for package in packages:
                        relpath = os.path.relpath(exclude, package)
                        if not relpath.startswith(".."):
                            exclude_package_data.setdefault(package, []).append(relpath)
            if packages and py_modules:
                raise ProjectError(
                    "Can't specify packages and py_modules at the same time."
                )
        return {
            "package_dir": {"": self.package_dir} if self.package_dir else {},
            "packages": packages,
            "py_modules": py_modules,
            "package_data": package_data,
            "exclude_package_data": exclude_package_data,
        }
