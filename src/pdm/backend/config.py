from __future__ import annotations

import glob
import os
import sys
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pdm.backend._vendor import tomli_w
from pdm.backend._vendor.pyproject_metadata import ConfigurationError, StandardMetadata
from pdm.backend.exceptions import ConfigError, ValidationError
from pdm.backend.structures import Table
from pdm.backend.utils import find_packages_iter, is_relative_path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import pdm.backend._vendor.tomli as tomllib

T = TypeVar("T")

if TYPE_CHECKING:
    from typing import TypedDict

    DataSpecDict = TypedDict(
        "DataSpecDict", {"path": str, "relative-to": str}, total=False
    )
    DataSpec = DataSpecDict | str


class Config:
    """The project config object for pdm backend.

    Parameters:
        root: The root directory of the project
        data: The parsed pyproject.toml data

    Attributes:
        metadata (Metadata): The project metadata from the `project` table
        build_config (BuildConfig): The build config from the `tool.pdm.build` table
    """

    def __init__(self, root: Path, data: dict[str, Any]) -> None:
        self.root = root
        self.data = data
        self.validate()

    def validate(self) -> StandardMetadata:
        """Validate the pyproject.toml data."""
        try:
            return StandardMetadata.from_pyproject(self.data, project_dir=self.root)
        except ConfigurationError as e:
            raise ValidationError(e.args[0], e.key) from e

    @property
    def metadata(self) -> dict[str, Any]:
        return self.data["project"]

    @cached_property
    def build_config(self) -> BuildConfig:
        return BuildConfig(
            self.root, self.data.setdefault("tool", {}).get("pdm", {}).get("build", {})
        )

    @classmethod
    def from_pyproject(cls, root: str | Path) -> Config:
        """Load the pyproject.toml file from the given project root."""
        root = Path(root)
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            raise ConfigError("pyproject.toml not found")
        with pyproject.open("rb") as fp:
            try:
                data = tomllib.load(fp)
            except tomllib.TOMLDecodeError as e:
                raise ConfigError(f"Invalid pyproject.toml file: {e}") from e
        return cls(root, data)

    def write_to(self, path: str | Path) -> None:
        """Write the pyproject.toml file to the given path."""
        with open(path, "wb") as fp:
            tomli_w.dump(self.data, fp)

    def for_hook(self, name: str) -> dict[str, Any]:
        """Return the config data for the given hook."""
        return self.build_config.get("hooks", {}).get(name, {})

    def convert_package_paths(self) -> dict[str, list | dict]:
        """Return a {package_dir, packages, package_data, exclude_package_data} dict."""
        packages = []
        py_modules = []
        package_data = {"": ["*"]}
        exclude_package_data: dict[str, list[str]] = {}
        package_dir = self.build_config.package_dir
        includes = self.build_config.includes
        excludes = self.build_config.excludes

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
                    temp = list(find_packages_iter(dir_name, src=package_dir or "."))
                    if os.path.isfile(os.path.join(dir_name, "__init__.py")):
                        temp.insert(
                            0,
                            os.path.relpath(dir_name, package_dir or None)
                            .replace("\\", ".")
                            .replace("/", "."),
                        )
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
            raise ConfigError("Can't specify packages and py_modules at the same time.")
        return {
            "package_dir": {"": package_dir} if package_dir else {},
            "packages": packages,
            "py_modules": py_modules,
            "package_data": package_data,
            "exclude_package_data": exclude_package_data,
        }


class BuildConfig(Table):
    """The `[tool.pdm.build]` table"""

    def __init__(self, root: Path, data: dict[str, Any]) -> None:
        self.root = root
        super().__init__(data)

    @property
    def custom_hook(self) -> str | None:
        """The relative path to the custom hook or None if not exists"""
        script = self.get("custom-hook", "pdm_build.py")
        if (self.root / script).exists():
            return script
        return None

    @property
    def includes(self) -> list[str]:
        """The includes setting"""
        return self.get("includes", [])

    @property
    def source_includes(self) -> list[str]:
        """The source-includes setting"""
        return self.get("source-includes", [])

    @property
    def excludes(self) -> list[str]:
        """The excludes setting"""
        return self.get("excludes", [])

    @property
    def run_setuptools(self) -> bool:
        """Whether to run setuptools"""
        return self.get("run-setuptools", False)

    def _get_default_package_dir(self) -> str:
        if (
            self.root.joinpath("src").is_dir()
            and not self.includes
            # the first path part must not be a wildcard
            or any(is_relative_path(Path(p), Path("src")) for p in self.includes)
            and "src" not in self.excludes
            and "src/" not in self.excludes
        ):
            return "src"
        return ""

    @property
    def package_dir(self) -> str:
        """A directory that will be used to looking for packages."""
        if "package-dir" in self:
            return self["package-dir"]
        return self._get_default_package_dir()

    @property
    def is_purelib(self) -> bool:
        """If not explicitly set, the project is considered to be non-pure
        if `build` exists.
        """
        return self.get("is-purelib", not bool(self.run_setuptools))

    @property
    def editable_backend(self) -> str:
        """Currently only two backends are supported:
        - editables: Proxy modules via editables
        - path: the legacy .pth file method(default)
        """
        return self.get("editable-backend", "path")

    @property
    def wheel_data(self) -> dict[str, list[DataSpec]]:
        """The wheel data configuration"""
        return self.get("wheel-data", {})
