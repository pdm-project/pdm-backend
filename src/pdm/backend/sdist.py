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
from pdm.backend.utils import normalize_file_permissions, safe_version, to_filename


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

    def get_files(self, context: Context) -> Iterable[tuple[str, Path]]:
        collected = dict(super().get_files(context))
        context.ensure_build_dir()
        context.config.write_to(context.build_dir / "pyproject.toml")
        collected["pyproject.toml"] = context.build_dir / "pyproject.toml"
        metadata = self.config.validate()

        def gen_additional_files() -> Iterable[str]:
            if local_hook := self.config.build_config.custom_hook:
                yield local_hook
            if metadata.readme and metadata.readme.file:
                yield metadata.readme.file.relative_to(self.location).as_posix()
            yield from self.find_license_files(metadata)

        root = self.location
        for file in gen_additional_files():
            if file in collected:
                continue
            if root.joinpath(file).exists():
                collected[file] = root / file
        return collected.items()

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

            pkg_info = str(self.config.validate().as_rfc822()).encode("utf-8")
            tar_info = tarfile.TarInfo(pjoin(dist_info, "PKG-INFO"))
            tar_info.size = len(pkg_info)
            tar_info = clean_tarinfo(tar_info)
            tar.addfile(tar_info, BytesIO(pkg_info))
            self._show_add_file("PKG-INFO", Path("PKG-INFO"))

        return target
