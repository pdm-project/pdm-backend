import hashlib
import os
import subprocess
import sys
import warnings
import zipfile
from base64 import urlsafe_b64encode
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, TextIO, Tuple, Union

from pdm.pep517.exceptions import BuildError, PDMWarning
from pdm.pep517.utils import is_relative_path, to_filename
from pdm.pep517.wheel import WheelBuilder


class EditableProject:
    """Copied from https://github.com/pfmoore/editables"""

    def __init__(self, project_name: str, project_dir: str) -> None:
        self.project_name = project_name
        self.project_dir = Path(project_dir)
        self.redirections: Dict[str, str] = {}
        self.path_entries: List[Path] = []

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

    def files(self) -> Iterable[Tuple[str, str]]:
        yield f"{self.project_name}.pth", self.pth_file()
        if self.redirections:
            yield f"__editables_{self.project_name}.py", self.bootstrap_file()

    def dependencies(self) -> Iterable[str]:
        if self.redirections:
            yield "editables"

    def pth_file(self) -> str:
        lines: List[str] = []
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
        self, location: Union[str, Path], config_settings: Optional[Mapping[str, Any]]
    ) -> None:
        super().__init__(location, config_settings=config_settings)
        self.editables = EditableProject(
            to_filename(self.meta.project_name), self.location.as_posix()
        )

    def _build(self, wheel: zipfile.ZipFile) -> None:
        if self.meta.build:
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
        self._prepare_editable()
        for name, content in self.editables.files():
            self._add_file_content(wheel, name, content)

    def _prepare_editable(self) -> None:
        package_paths = self.meta.convert_package_paths()
        package_dir = self.meta.package_dir
        if self.meta.editable_backend == "editables":
            for package in package_paths.get("packages", []):
                if "." in package:
                    continue
                self.editables.map(package, os.path.join(package_dir, package))

            for module in package_paths.get("py_modules", []):
                if "." in module:
                    continue

                patterns: Tuple[str, ...] = (f"{module}.py",)
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
            if self.meta.editable_backend == "editables":
                warnings.warn(
                    "editables backend is not available for namespace packages, "
                    "fallback to path entries",
                    PDMWarning,
                )
            self.editables.add_to_path(package_dir)

    def find_files_to_add(self, for_sdist: bool = False) -> List[Path]:
        package_paths = self.meta.convert_package_paths()
        package_dir = self.meta.package_dir
        redirections = [
            Path(package_dir, p.replace(".", "/")) for p in package_paths["packages"]
        ]
        return [
            p
            for p in super().find_files_to_add(for_sdist=for_sdist)
            if p.suffix not in (".py", ".pyc", ".pyo")
            and not any(is_relative_path(p, package) for package in redirections)
        ]

    def _add_file_content(
        self, wheel: zipfile.ZipFile, rel_path: str, content: str
    ) -> None:
        print(f" - Adding {rel_path}")
        zinfo = zipfile.ZipInfo(rel_path)

        hashsum = hashlib.sha256()
        buf = content.encode("utf-8")
        hashsum.update(buf)

        wheel.writestr(zinfo, buf, compress_type=zipfile.ZIP_DEFLATED)
        size = len(buf)
        hash_digest = urlsafe_b64encode(hashsum.digest()).decode("ascii").rstrip("=")

        self._records.append((rel_path, hash_digest, str(size)))

    def _write_metadata_file(self, fp: TextIO) -> None:
        self.meta._metadata.setdefault("dependencies", []).extend(
            self.editables.dependencies()
        )
        return super()._write_metadata_file(fp)
