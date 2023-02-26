from __future__ import annotations

import os
import tarfile
from copy import copy
from io import BytesIO
from pathlib import Path
from posixpath import join as pjoin
from typing import Iterable

from pdm.backend._vendor.packaging.utils import canonicalize_name
from pdm.backend.base import Builder
from pdm.backend.hooks import Context
from pdm.backend.utils import safe_version, to_filename


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

    if "SOURCE_DATE_EPOCH" in os.environ:
        ti.mtime = int(os.environ["SOURCE_DATE_EPOCH"])

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

    def get_files(self, context: Context) -> Iterable[tuple[str, Path]]:
        yield from super().get_files(context)
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
        root = self.location
        for file in additional_files:
            if root.joinpath(file).exists():
                yield file, root / file

    def build_artifact(
        self, context: Context, files: Iterable[tuple[str, Path]]
    ) -> Path:
        version = to_filename(safe_version(context.config.metadata["version"]))
        name = to_filename(canonicalize_name(context.config.metadata["name"]))
        dist_info = f"{name}-{version}"

        target = context.dist_dir / f"{dist_info}.tar.gz"

        with tarfile.open(target, mode="w:gz", format=tarfile.PAX_FORMAT) as tar:
            for relpath, path in files:
                tar_info = tar.gettarinfo(path, pjoin(dist_info, relpath))
                tar_info = clean_tarinfo(tar_info)
                if tar_info.isreg():
                    with path.open("rb") as f:
                        tar.addfile(tar_info, f)
                else:
                    tar.addfile(tar_info)
                self._show_add_file(relpath, path)

            pkg_info = self.format_pkginfo().encode("utf-8")
            tar_info = tarfile.TarInfo(pjoin(dist_info, "PKG-INFO"))
            tar_info.size = len(pkg_info)
            tar_info = clean_tarinfo(tar_info)
            tar.addfile(tar_info, BytesIO(pkg_info))
            self._show_add_file("PKG-INFO", Path("PKG-INFO"))

        return target
