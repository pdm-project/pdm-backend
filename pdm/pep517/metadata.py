import glob
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union

from ._vendor import toml
from .requirements import Requirement
from .utils import cd, find_packages_iter, safe_name


class ProjectError(ValueError):
    pass


class MetaField:
    def __init__(self, name, fget=None):
        self.name = name
        self.fget = fget

    def __get__(self, instance, owner):
        if not instance:
            return self
        try:
            rv = instance._metadata[self.name]
            if self.fget is not None:
                rv = self.fget(instance, rv)
            return rv
        except KeyError:
            return None


_NAME_EMAIL_RE = re.compile(r"^\s*([^<>]+?)\s*<([^<>]+)>")


class Metadata:
    """A class that holds all metadata that Python packaging requries."""

    def __init__(self, filepath: Union[str, Path]) -> None:
        self.filepath = Path(filepath).absolute()
        try:
            self._metadata = self._read_pyproject(self.filepath)
        except (FileNotFoundError, KeyError, toml.TomlDecodeError):
            raise ProjectError("The package is not a valid PDM project.")

    @staticmethod
    def _read_pyproject(filepath: Path) -> Dict[str, Any]:
        data = toml.loads(filepath.read_text(encoding="utf-8"))
        return data["tool"]["pdm"]

    def get_dependencies(self, section: str = "default") -> Dict[str, Requirement]:
        """Read the key:dep pairs from packages section."""
        section = "dependencies" if section == "default" else f"{section}-dependencies"
        packages = self._metadata.get(section, {})
        result = {}
        for name, req_dict in packages.items():
            req = Requirement.from_req_dict(name, req_dict)
            result[req.identify()] = req
        return result

    name: str = MetaField("name")

    def _get_version(self, value):
        if isinstance(value, str):
            return value
        version_source = value.get("from")
        with self.filepath.parent.joinpath(version_source).open(encoding="utf-8") as fp:
            version = re.findall(
                r"^__version__\s*=\s*[\"'](.+?)[\"']\s*$", fp.read(), re.M
            )[0]
        return version

    version: str = MetaField("version", _get_version)
    homepage: str = MetaField("homepage")
    license: str = MetaField("license")

    def _get_name(self, value):
        m = _NAME_EMAIL_RE.match(value)
        return m.group(1) if m else None

    def _get_email(self, value):
        m = _NAME_EMAIL_RE.match(value)
        return m.group(2) if m else None

    author: str = MetaField("author", _get_name)
    author_email: str = MetaField("author", _get_email)
    maintainer: str = MetaField("maintainer", _get_name)
    maintainer_email: str = MetaField("maintainer", _get_email)
    classifiers: List[str] = MetaField("classifiers")
    description: str = MetaField("description")
    keywords: str = MetaField("keywords")
    project_urls: Dict[str, str] = MetaField("project_urls")
    includes: List[str] = MetaField("includes")
    excludes: List[str] = MetaField("excludes")
    build: str = MetaField("build")

    @property
    def project_name(self) -> str:
        return safe_name(self.name)

    def _determine_content_type(self, value):
        if value.endswith(".md"):
            return "text/markdown"
        return None

    readme: str = MetaField("readme")
    long_description_content_type: str = MetaField("readme", _determine_content_type)
    _extras: List[str] = MetaField("extras")

    @property
    def install_requires(self) -> List[str]:
        # Exclude editable requirements for not supported in `install_requires`
        # field.
        return [r.as_line() for r in self.get_dependencies().values()]

    def _get_extra_require(self, extra: str) -> Tuple[str, Iterable[Requirement]]:
        if "=" in extra:
            name, extras = extra.split("=")
            name = name.strip()
            extras = [e.strip() for e in extras.strip().split("|")]
        else:
            name, extras = extra, [extra]
        extra_require = {}
        for extra in extras:
            extra_require.update(self.get_dependencies(extra))
        return name, extra_require.values()

    @property
    def extras_require(self) -> Dict[str, List[str]]:
        """For setup.py extras_require field"""
        if not self._extras:
            return {}
        return {
            name: [r.as_line() for r in reqs]
            for extra in self._extras
            for name, reqs in [self._get_extra_require(extra)]
        }

    @property
    def requires_extra(self) -> Dict[str, List[str]]:
        """For PKG-INFO metadata"""
        if not self._extras:
            return {}
        result = {}
        for extra in self._extras:

            name, reqs = self._get_extra_require(extra)
            current = result[name] = []
            for r in reqs:
                if not r.marker:
                    r.marker = f"extra == {name!r}"
                elif " or " in r.marker:
                    r.marker = f"({r.marker}) and extra == {name!r}"
                else:
                    r.marker = f"{r.marker} and extra == {name!r}"
                current.append(r.as_line())
        return result

    @property
    def python_requires(self) -> str:
        return self._metadata.get("python_requires", "")

    @property
    def entry_points(self) -> Dict[str, List[str]]:
        result = {}
        settings = self._metadata
        if "cli" in settings:
            result["console_scripts"] = [
                f"{key} = {value}" for key, value in settings["cli"].items()
            ]
        if "entry_points" in settings:
            for plugin, value in settings["entry_points"].items():
                result[plugin] = [f"{k} = {v}" for k, v in value.items()]
        return result

    def convert_package_paths(self) -> Dict[str, Union[List, Dict]]:
        """Return a {package_dir, packages, package_data, exclude_package_data} dict."""
        package_dir = {}
        packages = []
        py_modules = []
        package_data = {"": ["*"]}
        exclude_package_data = {}

        with cd(self.filepath.parent.as_posix()):
            if not self.includes:
                if os.path.isdir("src"):
                    package_dir[""] = "src"
                    packages = list(find_packages_iter("src"))
                else:
                    packages = list(find_packages_iter(exclude=["tests", "tests.*"]))
                if not packages:
                    py_modules = [path[:-3] for path in glob.glob("*.py")]
            else:
                packages_set = set()
                includes = self.includes
                for include in includes[:]:
                    if include.replace("\\", "/").endswith("/*"):
                        include = include[:-2]
                    if "*" not in include and os.path.isdir(include):
                        dir_name = include.rstrip("/\\")
                        temp = list(find_packages_iter(dir_name))
                        if os.path.exists(dir_name + "/__init__.py"):
                            temp = [dir_name] + [f"{dir_name}.{part}" for part in temp]
                        elif temp:
                            package_dir[""] = dir_name
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
            "package_dir": package_dir,
            "packages": packages,
            "py_modules": py_modules,
            "package_data": package_data,
            "exclude_package_data": exclude_package_data,
        }
