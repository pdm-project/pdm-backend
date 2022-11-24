from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pdm.backend._vendor import tomli
from pdm.backend._vendor.validate_pyproject import api, errors
from pdm.backend.exceptions import PDMWarning, ProjectError, ValidationError
from pdm.backend.structures import Table
from pdm.backend.utils import show_warning
from pdm.backend._vendor.pyproject_metadata import StandardMetadata


class Config:
    def __init__(self, root: Path, data: dict[str, Any]) -> None:
        self.validate(data)
        self.root = root
        self.data = data
        self.metadata = Metadata(data["project"])
        self.backend_config = BackendConfig(
            root, data.setdefault("tool", {}).get("pdm", {})
        )

    def as_standard_metadata(self) -> StandardMetadata:
        return StandardMetadata.from_pyproject(self.data, project_dir=self.root)

    @staticmethod
    def validate(data: dict[str, Any]) -> None:
        validator = api.Validator()
        try:
            validator(data)
        except errors.ValidationError as e:
            raise ValidationError(e.summary, e.details) from e

    @classmethod
    def from_pyproject(cls, root: Path) -> Config:
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            raise ProjectError("pyproject.toml not found")
        with pyproject.open("rb") as fp:
            try:
                data = tomli.load(fp)
            except tomli.TOMLDecodeError as e:
                raise ProjectError(f"Invalid pyproject.toml file: {e}") from e
        return cls(root, data)


class Metadata(Table):
    @property
    def readme_file(self) -> str | None:
        readme = self.get("readme")
        if not readme:
            return None
        if isinstance(readme, str):
            return readme
        if isinstance(readme, dict) and "file" in readme:
            return readme["file"]
        return None

    @property
    def license_files(self) -> dict[str, list[str]]:
        subtable_files = None
        if (
            "license" in self
            and isinstance(self["license"], dict)
            and "files" in self["license"]
        ):
            subtable_files = self["license"]["files"]
        if "license-files" not in self:
            if subtable_files is not None:
                return {"paths": [self["license"]["file"]]}
            return {
                "globs": [
                    "LICENSES/*",
                    "LICEN[CS]E*",
                    "COPYING*",
                    "NOTICE*",
                    "AUTHORS*",
                ]
            }
        if subtable_files is not None:
            raise ValidationError(
                "license-files",
                "Can't specify both 'license.files' and 'license-files' fields",
            )
        rv = self["license-files"]
        valid_keys = {"globs", "paths"} & set(rv)
        if len(valid_keys) == 2:
            raise ValidationError(
                "license-files", "Can't specify both 'paths' and 'globs'"
            )
        if not valid_keys:
            raise ValidationError("license-files", "Must specify 'paths' or 'globs'")
        return rv


class BackendConfig(Table):
    """The [tool.pdm] table"""

    def __init__(self, root: Path, data: dict[str, Any]) -> None:
        self.root = root
        super().__init__(data)

    def _build_config(self, name: str, default: Any = None) -> Any:
        return self.get("build", {}).get(name, default)

    @property
    def includes(self) -> list[str]:
        return self._build_config("includes", [])

    @property
    def source_includes(self) -> list[str]:
        return self._build_config("source-includes", [])

    @property
    def excludes(self) -> list[str]:
        return self._build_config("excludes", [])

    @property
    def setup_script(self) -> str | None:
        build_table = self.get("build", {})
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
        build = self.get("build", {})
        return isinstance(build, str) or cast(dict, build).get("run-setuptools", False)

    @property
    def package_dir(self) -> str:
        """A directory that will be used to looking for packages."""
        default = "src" if self.root.joinpath("src").exists() else ""
        return self._build_config("package-dir", default)

    @property
    def is_purelib(self) -> bool:
        """If not explicitly set, the project is considered to be non-pure
        if `build` exists.
        """
        return self._build_config("is-purelib", not bool(self.run_setuptools))

    @property
    def editable_backend(self) -> str:
        """Currently only two backends are supported:
        - editables: Proxy modules via editables
        - path: the legacy .pth file method(default)
        """
        return self._build_config("editable-backend", "path")
