from __future__ import annotations

import os
import warnings
from pathlib import Path

from editables import EditableProject

from pdm.backend.exceptions import ConfigError, PDMWarning
from pdm.backend.hooks.base import Context
from pdm.backend.utils import safe_name, to_filename
from pdm.backend.wheel import WheelBuilder


def is_subpath(path: str, parent: str) -> bool:
    return os.path.normcase(path).startswith(os.path.normcase(parent))


class EditableBuildHook:
    @staticmethod
    def editable_version(version: str) -> str:
        if "+" in version:
            return f"{version}.editable"
        return f"{version}+editable"

    def pdm_build_initialize(self, context: Context) -> None:
        editables = self._prepare_editable(context)
        context.config.metadata.setdefault("dependencies", []).extend(
            editables.dependencies()
        )
        version = context.config.metadata["version"]
        context.config.metadata["version"] = self.editable_version(version)
        context.editables = editables

    def pdm_build_update_files(self, context: Context, files: dict[str, Path]) -> None:
        packages: list[str] = context.config.convert_package_paths()["packages"]
        proxied = {p.replace(".", "/") for p in packages}
        for relpath in list(files):
            if os.path.splitext(relpath)[1] in (".py", ".pyc", ".pyo"):
                # All .py[cod] files are proxied
                del files[relpath]
            elif any(is_subpath(relpath, p) for p in proxied):
                # also exclude data files in proxied packages
                del files[relpath]
        editables: EditableProject = context.editables
        context.ensure_build_dir()
        for name, content in editables.files():
            with open(os.path.join(context.build_dir, name), "w", newline="") as f:
                f.write(content)
            files[name] = context.build_dir.joinpath(name)

    def _prepare_editable(self, context: Context) -> EditableProject:
        config = context.config
        try:
            editables = EditableProject(
                to_filename(safe_name(config.metadata["name"])),
                context.root.as_posix(),
            )
        except ValueError as e:
            raise ConfigError(str(e)) from None
        package_paths = config.convert_package_paths()
        build_config = config.build_config
        package_dir = build_config.package_dir
        if build_config.editable_backend == "editables":
            for package in package_paths.get("packages", []):
                if "." in package:
                    continue
                editables.map(package, os.path.join(package_dir, package))

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
                        editables.map(module, path.as_posix())
                        break

        if not editables.redirections:
            # For implicit namespace packages, modules cannot be mapped.
            # Fallback to .pth method in this case.
            if build_config.editable_backend == "editables":
                warnings.warn(
                    "editables backend is not available for namespace packages, "
                    "fallback to path entries",
                    PDMWarning,
                )
            editables.add_to_path(package_dir)
        return editables


class EditableBuilder(WheelBuilder):
    target = "editable"
    hooks = WheelBuilder.hooks + [EditableBuildHook()]
