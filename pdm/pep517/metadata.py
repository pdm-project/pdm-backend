import glob
import os
import re
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
)

from pdm.pep517._vendor import toml
from pdm.pep517._vendor.packaging.requirements import Requirement
from pdm.pep517._vendor.packaging.specifiers import SpecifierSet
from pdm.pep517._vendor.packaging.version import Version
from pdm.pep517.legacy import convert_legacy
from pdm.pep517.license import get_license_classifier, license_lookup
from pdm.pep517.scm import get_version_from_scm
from pdm.pep517.utils import (
    cd,
    ensure_pep440_req,
    find_packages_iter,
    is_dict_like,
    merge_marker,
    safe_name,
)
from pdm.pep517.validator import validate_pep621

T = TypeVar("T")

AVAILABLE_PYTHON_VERSIONS = (
    "2.7",
    "3.4",
    "3.5",
    "3.6",
    "3.7",
    "3.8",
    "3.9",
)


class ProjectError(ValueError):
    pass


class MetaField(Generic[T]):
    def __init__(
        self, name: str, fget: Optional[Callable[["Metadata", Any], T]] = None
    ) -> None:
        self.name = name
        self.fget = fget

    def __get__(self, instance: "Metadata", owner: Type["Metadata"]) -> T:
        if instance is None:
            return self
        try:
            rv = instance._metadata[self.name]
            if self.fget is not None:
                rv = self.fget(instance, rv)
            return rv
        except KeyError:
            return None


class Metadata:
    """A class that holds all metadata that Python packaging requries."""

    DEFAULT_ENCODING = "utf-8"
    SUPPORTED_CONTENT_TYPES = ("text/markdown", "text/x-rst", "text/plain")

    def __init__(
        self, filepath: Union[str, Path], data: Optional[Mapping] = None
    ) -> None:
        self.filepath = Path(filepath).absolute()
        self._tool_settings = {}
        self._metadata = data
        if self._metadata is None:
            self._read_pyproject()

    def _read_pyproject(self) -> Dict[str, Any]:
        try:
            data = toml.loads(self.filepath.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ProjectError("pyproject.toml does not exist.")
        except toml.TomlDecodeError:
            raise ProjectError("The project's pyproject.toml is not valid.")
        else:
            if "tool" in data and "pdm" in data["tool"]:
                self._tool_settings = data["tool"]["pdm"]
            if "project" in data:
                self._metadata = data["project"]
            elif self._tool_settings:
                # TODO: deprecate legacy format
                self._metadata = convert_legacy(self._tool_settings)
            else:
                raise ProjectError("No [project] config in pyproject.toml")

    def validate(self, raising: bool = False) -> bool:
        return validate_pep621(self._metadata, raising)

    name: MetaField[str] = MetaField("name")

    def _get_version(self, value):
        if isinstance(value, str):
            return value
        if not self.dynamic or "version" not in self.dynamic:
            raise ProjectError(
                "'value' must be in 'dynamic' field to let pdm-pep517 fill in the value"
            )
        version_source = value.get("from")
        if version_source:
            with self.filepath.parent.joinpath(version_source).open(
                encoding="utf-8"
            ) as fp:
                version = re.findall(
                    r"^__version__\s*=\s*[\"'](.+?)[\"']\s*$", fp.read(), re.M
                )[0]
        elif value.get("use_scm", False):
            version = get_version_from_scm(self.filepath.parent)
        else:
            version = None
        return version

    version: MetaField[str] = MetaField("version", _get_version)
    description: MetaField[str] = MetaField("description")

    def _get_readme_file(self, value):
        if is_dict_like(value):
            return value.get("file")
        return value

    def _get_readme_content(self, value):
        if is_dict_like(value):
            if "file" in value and "text" in value:
                raise ProjectError(
                    "readme table shouldn't specify both 'file' "
                    "and 'text' at the same time"
                )
            if "text" in value:
                return value["text"]
            file_path = value.get("file")
            encoding = value.get("charset", self.DEFAULT_ENCODING)
            return Path(file_path).read_text(encoding=encoding)
        return Path(value).read_text(encoding=self.DEFAULT_ENCODING)

    def _get_content_type(self, value):
        if is_dict_like(value):
            content_type = value.get("content-type")
            if not content_type:
                raise ProjectError("'content-type' is missing in the readme table")
            if content_type not in self.SUPPORTED_CONTENT_TYPES:
                raise ProjectError(f"Unsupported readme content-type: {content_type}")
            return content_type
        if value.lower().endswith(".md"):
            return "text/markdown"
        elif value.lower().endswith(".rst"):
            return "text/x-rst"
        raise ProjectError(f"Unsupported readme suffix: {value}")

    readme: MetaField[str] = MetaField("readme", _get_readme_file)
    long_description: MetaField[str] = MetaField("readme", _get_readme_content)
    long_description_content_type: MetaField[str] = MetaField(
        "readme", _get_content_type
    )

    def _get_license(self, value):
        if not is_dict_like(value):
            return ""
        if "file" in value and "text" in value:
            raise ProjectError(
                "license table shouldn't specify both 'file' "
                "and 'text' at the same time"
            )
        return (
            Path(value["file"]).read_text(encoding=self.DEFAULT_ENCODING)
            if "file" in value
            else value.get("text")
        )

    def _get_license_type(self, value):
        if is_dict_like(value):
            if value.get("text", "") in license_lookup:
                return value.get("text")
        else:
            return value

    license: MetaField[str] = MetaField("license", _get_license)
    license_type: MetaField[str] = MetaField("license", _get_license_type)

    def _get_name(self, value):
        result = []
        for item in value:
            if "email" not in item and "name" in item:
                result.append(item.get("name"))
        return ",".join(result)

    def _get_email(self, value):
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
    def classifiers(self):
        classifers = set(self._metadata.get("classifiers", []))

        if self.dynamic and "classifiers" in self.dynamic:
            python_constraint = (
                SpecifierSet(self.requires_python)
                if self.requires_python
                else SpecifierSet()
            )

            for version in AVAILABLE_PYTHON_VERSIONS:
                if python_constraint.contains(Version(version)):
                    classifers.add(f"Programming Language :: Python :: {version[0]}")
                    classifers.add(f"Programming Language :: Python :: {version}")

            if self.license_type:
                classifers.add(get_license_classifier(self.license_type))

        return sorted(classifers)

    keywords: MetaField[str] = MetaField("keywords")
    project_urls: MetaField[Dict[str, str]] = MetaField("urls")

    # Deprecate legacy metadata location
    @property
    def includes(self) -> List[str]:
        if "includes" in self._metadata:
            return self._metadata["includes"]
        elif "includes" in self._tool_settings:
            return self._tool_settings["includes"]
        return []

    @property
    def source_includes(self) -> List[str]:
        return self._tool_settings.get("source-includes", [])

    @property
    def excludes(self) -> List[str]:
        if "excludes" in self._metadata:
            return self._metadata["excludes"]
        elif "excludes" in self._tool_settings:
            return self._tool_settings["excludes"]
        return []

    @property
    def build(self) -> Optional[str]:
        if "build" in self._metadata:
            return self._metadata["build"]
        elif "build" in self._tool_settings:
            return self._tool_settings["build"]
        return None

    @property
    def package_dir(self) -> str:
        """A directory that will be used to looking for packages."""
        if "package-dir" in self._metadata:
            return self._metadata["package-dir"]
        elif "package-dir" in self._tool_settings:
            return self._tool_settings["package-dir"]
        elif self.filepath.parent.joinpath("src").is_dir():
            return "src"
        return ""

    def _convert_dependencies(self, deps):
        return list(filter(None, map(ensure_pep440_req, deps)))

    def _convert_optional_dependencies(self, deps):
        return {k: self._convert_dependencies(deps[k]) for k in deps}

    dependencies: MetaField[List[str]] = MetaField(
        "dependencies", _convert_dependencies
    )
    optional_dependencies: MetaField[Dict[str, List[str]]] = MetaField(
        "optional-dependencies", _convert_optional_dependencies
    )
    dynamic: MetaField[List[str]] = MetaField("dynamic")

    @property
    def project_name(self) -> str:
        return safe_name(self.name)

    @property
    def requires_extra(self) -> Dict[str, List[str]]:
        """For PKG-INFO metadata"""
        if not self.optional_dependencies:
            return {}
        result = {}
        for name, reqs in self.optional_dependencies.items():
            current = result[name] = []
            for r in reqs:
                parsed = Requirement(r)
                merge_marker(parsed, f"extra == {name!r}")
                current.append(str(parsed))
        return result

    @property
    def requires_python(self) -> str:
        return self._metadata.get("requires-python", "")

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
                    raise ProjectError(
                        f"'project.entry-points.{plugin}'' should be defined "
                        f"in 'project.{plugin.replace('_', '-')}'"
                    )
                result[plugin] = [f"{k} = {v}" for k, v in value.items()]
        return result

    def convert_package_paths(self) -> Dict[str, Union[List, Dict]]:
        """Return a {package_dir, packages, package_data, exclude_package_data} dict."""
        packages = []
        py_modules = []
        package_data = {"": ["*"]}
        exclude_package_data = {}

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
                includes = self.includes
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
                    for path in glob.glob(include):
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
