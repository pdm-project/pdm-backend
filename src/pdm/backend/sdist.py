from __future__ import annotations

import os
import tarfile
from collections.abc import Iterable
from copy import copy
from io import BytesIO
from itertools import dropwhile
from pathlib import Path
from posixpath import join as pjoin
from typing import Any

from pdm.backend._vendor.packaging.utils import canonicalize_name
from pdm.backend.base import Builder
from pdm.backend.hooks import Context
from pdm.backend.utils import normalize_file_permissions, safe_version, to_filename

_EXTERNAL_FILES_DIR = ".pdm-external"


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

    def _normalize_file_path(self, path: Path) -> str:
        relative_path = Path(os.path.relpath(path, self.location))
        if relative_path.parts[0] != os.pardir:
            return relative_path.as_posix()

        local_parts = tuple(
            dropwhile(lambda part: part == os.pardir, relative_path.parts)
        )
        return Path(_EXTERNAL_FILES_DIR, *local_parts).as_posix()

    def get_files(self, context: Context) -> Iterable[tuple[str, Path]]:
        collected = dict(super().get_files(context))
        context.ensure_build_dir()
        metadata = self.config.validate()
        self._metadata = metadata
        project_data = context.config.data["project"]

        def set_file_reference(field: str, path: str) -> None:
            value: Any = project_data[field]
            if isinstance(value, str):
                project_data[field] = path
            else:
                value["file"] = path

        def gen_additional_files() -> Iterable[tuple[str, Path]]:
            if local_hook := self.config.build_config.custom_hook:
                yield local_hook, self.location / local_hook
            if metadata.readme and metadata.readme.file:
                path = self._normalize_file_path(metadata.readme.file)
                set_file_reference("readme", path)
                yield path, metadata.readme.file
            license_file = getattr(metadata.license, "file", None)
            for file in self.find_license_files(metadata):
                source = self.location / file
                path = self._normalize_file_path(source)
                if license_file is not None and source == license_file:
                    set_file_reference("license", path)
                yield path, source

        for path, source in gen_additional_files():
            if collected.get(path) == source:
                continue
            if source.exists():
                collected[path] = source

        pyproject_path = context.build_dir / "pyproject.toml"
        context.config.write_to(pyproject_path)
        collected["pyproject.toml"] = pyproject_path
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

            pkg_info = str(self._metadata.as_rfc822()).encode("utf-8")
            tar_info = tarfile.TarInfo(pjoin(dist_info, "PKG-INFO"))
            tar_info.size = len(pkg_info)
            tar_info = clean_tarinfo(tar_info)
            tar.addfile(tar_info, BytesIO(pkg_info))
            self._show_add_file("PKG-INFO", Path("PKG-INFO"))

        return target
