from __future__ import annotations

import os
import tarfile
import tempfile
from copy import copy
from pathlib import Path
from typing import Iterable

from pdm.backend.base import Builder
from pdm.backend.hooks import Context
from pdm.backend.structures import FileMap


def normalize_file_permissions(st_mode: int) -> int:
    """
    Normalizes the permission bits in the st_mode field from stat to 644/755

    Popular VCSs only track whether a file is executable or not. The exact
    permissions can vary on systems with different umasks. Normalising
    to 644 (non executable) or 755 (executable) makes builds more reproducible.
    """
    # Set 644 permissions, leaving higher bits of st_mode unchanged
    new_mode = (st_mode | 0o644) & ~0o133
    if st_mode & 0o100:
        new_mode |= 0o111  # Executable: 644 -> 755

    return new_mode


def clean_tarinfo(tar_info: tarfile.TarInfo) -> tarfile.TarInfo:
    """
    Clean metadata from a TarInfo object to make it more reproducible.

        - Set uid & gid to 0
        - Set uname and gname to ""
        - Normalise permissions to 644 or 755
        - Set mtime if not None
    """
    ti = copy(tar_info)
    ti.uid = 0
    ti.gid = 0
    ti.uname = ""
    ti.gname = ""
    ti.mode = normalize_file_permissions(ti.mode)

    return ti


class SdistBuilder(Builder):
    """This build should be performed for PDM project only."""

    target = "sdist"

    def initialize(self, context: Context) -> None:
        super().initialize(context)
        # Save the config to build_dir/pyprojec.toml so that any
        # modification to the pyproject.toml will be saved in the sdist.
        context.ensure_build_dir()
        context.config.write_to(context.build_dir / "pyproject.toml")

    def _collect_files(self, context: Context, root: Path) -> FileMap:
        files = super()._collect_files(context, root)
        local_hook = self.config.build_config.custom_hook

        additional_files: Iterable[str] = filter(
            None,
            (
                local_hook,
                self.config.metadata.readme_file,
                "pyproject.toml",
                *self.find_license_files(),
            ),
        )

        for file in additional_files:
            if root.joinpath(file).exists():
                files[file] = root / file

        return files

    def build_artifact(
        self, context: Context, files: Iterable[tuple[str, Path]]
    ) -> Path:
        version: str = context.config.metadata["version"]
        dist_info = f"{context.config.metadata['name']}-{version}"

        target = context.dist_dir / f"{dist_info}.tar.gz"
        tar = tarfile.open(target, mode="w:gz", format=tarfile.PAX_FORMAT)

        try:
            for relpath, path in files:
                tar.add(
                    path,
                    arcname=os.path.join(dist_info, relpath),
                    recursive=False,
                )
                self._show_add_file(relpath, path)

            fd, temp_name = tempfile.mkstemp(prefix="pkg-info")
            pkg_info = self.format_pkginfo().encode("utf-8")
            with open(fd, "wb") as f:
                f.write(pkg_info)
            tar.add(
                temp_name, arcname=os.path.join(dist_info, "PKG-INFO"), recursive=False
            )
            self._show_add_file("PKG-INFO", Path("PKG-INFO"))
        finally:
            tar.close()

        return target
