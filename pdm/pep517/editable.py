from __future__ import annotations

import os
import subprocess
import sys
import tokenize
import warnings
from pathlib import Path
from typing import Any, Iterable, Mapping, TextIO

from pdm.pep517.exceptions import BuildError, PDMWarning
from pdm.pep517.utils import is_relative_path, show_warning, to_filename
from pdm.pep517.wheel import WheelBuilder


class EditableProject:
    """Copied from https://github.com/pfmoore/editables"""

    def __init__(self, project_name: str, project_dir: str) -> None:
        self.project_name = project_name
        self.project_dir = Path(project_dir)
        self.redirections: dict[str, str] = {}
        self.path_entries: list[Path] = []

    def make_absolute(self, path: str) -> Path:
        return (self.project_dir / path).resolve()

    def map(self, name: str, target: str) -> None:
        if "." in name:
            raise BuildError(f"Cannot map {name} as it is not a top-level package")
        abs_target = self.make_absolute(target)
        if abs_target.is_dir():
            abs_target = abs_target / "__init__.py"
        if abs_target.is_file():
            self.redirections[name] = str(abs_target)
        else:
            raise BuildError(f"{target} is not a valid Python package or module")

    def add_to_path(self, dirname: str) -> None:
        self.path_entries.append(self.make_absolute(dirname))

    def files(self) -> Iterable[tuple[str, str]]:
        yield f"{self.project_name}.pth", self.pth_file()
        if self.redirections:
            yield f"__editables_{self.project_name}.py", self.bootstrap_file()

    def dependencies(self) -> Iterable[str]:
        if self.redirections:
            yield "editables"

    def pth_file(self) -> str:
        lines: list[str] = []
        if self.redirections:
            lines.append(f"import __editables_{self.project_name}")
        for entry in self.path_entries:
            lines.append(str(entry))
        return "\n".join(lines)

    def bootstrap_file(self) -> str:
        bootstrap = [
            "from editables.redirector import RedirectingFinder as F",
            "F.install()",
        ]
        for name, path in self.redirections.items():
            bootstrap.append(f"F.map_module({name!r}, {path!r})")
        return "\n".join(bootstrap)


class EditableBuilder(WheelBuilder):
    def __init__(
        self, location: str | Path, config_settings: Mapping[str, Any] | None
    ) -> None:
        super().__init__(location, config_settings=config_settings)
        assert self.meta.project_name, "Project name is not specified"
        self.editables = EditableProject(
            to_filename(self.meta.project_name), self.location.as_posix()
        )

    def _build(self) -> None:
        if self.meta.config.setup_script:
            if self.meta.config.run_setuptools:
                setup_py = self.ensure_setup_py()
                build_args = [
                    sys.executable,
                    str(setup_py),
                    "build_ext",
                    "--inplace",
                ]
                try:
                    subprocess.check_call(build_args)
                except subprocess.CalledProcessError as e:
                    raise BuildError(f"Error occurs when running {build_args}:\n{e}")
            else:
                build_dir = self.location / self.meta.config.package_dir
                with tokenize.open(self.meta.config.setup_script) as f:
                    code = compile(f.read(), self.meta.config.setup_script, "exec")
                global_dict: dict[str, Any] = {}
                exec(code, global_dict)
                if "build" not in global_dict:
                    show_warning(
                        "No build() function found in the setup script, do nothing",
                        PDMWarning,
                    )
                    return
                global_dict["build"](str(self.location), str(build_dir))

        self._prepare_editable()
        for name, content in self.editables.files():
            with self._open_for_write(name) as fp:
                fp.write(content)

    def _prepare_editable(self) -> None:
        package_paths = self.meta.convert_package_paths()
        package_dir = self.meta.config.package_dir
        if self.meta.config.editable_backend == "editables":
            for package in package_paths.get("packages", []):
                if "." in package:
                    continue
                self.editables.map(package, os.path.join(package_dir, package))

            for module in package_paths.get("py_modules", []):
                if "." in module:
                    continue

                patterns: tuple[str, ...] = (f"{module}.py",)
                if os.name == "nt":
                    patterns += (f"{module}.*.pyd",)
                else:
                    patterns += (f"{module}.*.so",)
                for pattern in patterns:
                    path = next(Path(package_dir).glob(pattern), None)
                    if path:
                        self.editables.map(module, path.as_posix())
                        break

        if not self.editables.redirections:
            # For implicit namespace packages, modules cannot be mapped.
            # Fallback to .pth method in this case.
            if self.meta.config.editable_backend == "editables":
                warnings.warn(
                    "editables backend is not available for namespace packages, "
                    "fallback to path entries",
                    PDMWarning,
                )
            self.editables.add_to_path(package_dir)

    def find_files_to_add(self, for_sdist: bool = False) -> list[Path]:
        package_paths = self.meta.convert_package_paths()
        package_dir = self.meta.config.package_dir
        redirections = [
            Path(package_dir, p.replace(".", "/")) for p in package_paths["packages"]
        ]
        return [
            p
            for p in super().find_files_to_add(for_sdist=for_sdist)
            if p.suffix not in (".py", ".pyc", ".pyo")
            and not any(is_relative_path(p, package) for package in redirections)
        ]

    def _write_metadata_file(self, fp: TextIO) -> None:
        self.meta.data.setdefault("dependencies", []).extend(
            self.editables.dependencies()
        )
        return super()._write_metadata_file(fp)
