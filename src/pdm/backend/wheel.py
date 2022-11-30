from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import shutil
import stat
import tempfile
import zipfile
from base64 import urlsafe_b64encode
from pathlib import Path
from typing import IO, Any, Iterable, Mapping, NamedTuple, cast

from pdm.backend import __version__
from pdm.backend._vendor.packaging import tags
from pdm.backend._vendor.packaging.specifiers import SpecifierSet
from pdm.backend.base import Builder
from pdm.backend.hooks import Context
from pdm.backend.hooks.setuptools import SetuptoolsBuildHook
from pdm.backend.structures import FileMap
from pdm.backend.utils import (
    expand_vars,
    get_abi_tag,
    get_platform,
    safe_name,
    safe_version,
    to_filename,
)

WHEEL_FILE_FORMAT = (
    """\
Wheel-Version: 1.0
Generator: pdm-backend %s
Root-Is-Purelib: {is_purelib}
Tag: {tag}
"""
    % __version__
)

PY_LIMITED_API_PATTERN = r"cp3\d{1,2}"
# Fix the date time for reproducible builds
ZIPINFO_DEFAULT_DATE_TIME = (2016, 1, 1, 0, 0, 0)


def _open_for_write(path: str | Path) -> IO[str]:
    """A simple wrapper around open() that preserves the line ending styles"""
    return open(path, "w", newline="", encoding="utf-8")


class RecordEntry(NamedTuple):
    relpath: str
    hash_digest: str
    size: str


class WheelBuilder(Builder):
    target = "wheel"
    hooks = Builder.hooks + [SetuptoolsBuildHook()]

    def __init__(
        self, location: str | Path, config_settings: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(location, config_settings)
        self.__tag: str | None = None

    def _get_platform_tags(self) -> tuple[str | None, str | None, str | None]:
        python_tag: str | None = None
        py_limited_api: str | None = None
        plat_name: str | None = None
        if not self.config_settings:
            return python_tag, py_limited_api, plat_name
        if "--python-tag" in self.config_settings:
            python_tag = self.config_settings["--python-tag"]
        if "--py-limited-api" in self.config_settings:
            py_limited_api = cast(str, self.config_settings["--py-limited-api"])
            if not re.match(PY_LIMITED_API_PATTERN, py_limited_api):
                raise ValueError(
                    "py-limited-api must match '%s'" % PY_LIMITED_API_PATTERN
                )
        if "--plat-name" in self.config_settings:
            plat_name = self.config_settings["--plat-name"]
        return python_tag, py_limited_api, plat_name

    def prepare_metadata(self, metadata_directory: str) -> Path:
        """Write the dist-info files under the given directory"""
        context = self.build_context(Path(metadata_directory))
        self.initialize(context)
        return self._write_dist_info(Path(metadata_directory))

    def initialize(self, context: Context) -> None:
        self._fix_dependencies()
        return super().initialize(context)

    def _fix_dependencies(self) -> None:
        """Fix the dependencies and remove dynamic variables from the metadata"""
        metadata = self.config.metadata
        root = self.location.as_posix()
        if metadata.get("dependencies"):
            metadata["dependencies"] = [
                expand_vars(dep, root) for dep in metadata["dependencies"]
            ]
        if metadata.get("optional-dependencies"):
            for name, deps in metadata["optional-dependencies"].items():
                metadata["optional-dependencies"][name] = [
                    expand_vars(dep, root) for dep in deps
                ]

    def _collect_files(self, context: Context, root: Path) -> FileMap:
        files = super()._collect_files(context, root)
        if root == self.location:
            self._fix_package_dir(files)
            files.update(self._get_metadata_files(context))
        return files

    def _fix_package_dir(self, files: FileMap) -> None:
        """remove the package-dir part from the relative paths"""
        package_dir = self.config.build_config.package_dir
        if not package_dir:
            return
        common_prefix = f"{package_dir}/"
        for rel_path, full_path in list(files.items()):
            if rel_path.startswith(common_prefix):
                files[rel_path[len(common_prefix) :]] = full_path
                del files[rel_path]

    def build_artifact(
        self, context: Context, files: Iterable[tuple[str, Path]]
    ) -> Path:
        records: list[RecordEntry] = []
        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as fp:
            with zipfile.ZipFile(fp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for rel_path, full_path in files:
                    records.append(self._add_file_to_zip(zf, rel_path, full_path))
                self._write_record(zf, records)

        target = context.dist_dir / f"{self.name_version}-{self.tag}.whl"
        if target.exists():
            target.unlink()
        shutil.move(fp.name, target)
        return target

    @property
    def name_version(self) -> str:
        name = to_filename(safe_name(self.config.metadata["name"]))
        version = to_filename(safe_version(self.config.metadata["version"]))
        return f"{name}-{version}"

    @property
    def dist_info_name(self) -> str:
        return f"{self.name_version}.dist-info"

    @property
    def tag(self) -> str:
        if self.__tag is None:
            self.__tag = self._get_tag()
        return self.__tag

    def _get_tag(self) -> str:
        impl, abi, platform = self._get_platform_tags()
        is_purelib = self.config.build_config.is_purelib
        if not is_purelib:
            if not platform:
                platform = get_platform(self.location / "build")
            if not impl:
                impl = tags.interpreter_name() + tags.interpreter_version()
            if abi and impl.startswith("cp3"):  # type: ignore[union-attr]
                impl = abi
                abi_tag = "abi3"
            else:
                abi_tag = str(get_abi_tag()).lower()
        else:
            if not platform:
                platform = "any"
            abi_tag = "none"
            if not impl:
                requires_python = self.config.metadata.get("requires-python", "")
                if SpecifierSet(requires_python).contains("2.7"):
                    impl = "py2.py3"
                else:
                    impl = "py3"

        platform = platform.lower().replace("-", "_").replace(".", "_")  # type: ignore
        tag = (impl, abi_tag, platform)
        if not is_purelib:
            supported_tags = [(t.interpreter, t.abi, platform) for t in tags.sys_tags()]
            assert (
                tag in supported_tags
            ), f"would build wheel with unsupported tag {tag}"
        return "-".join(tag)  # type: ignore[arg-type]

    def _write_dist_info(self, parent: Path) -> Path:
        """write the dist-info directory and return the path to it"""
        dist_info = parent / self.dist_info_name
        dist_info.mkdir(0o700, parents=True, exist_ok=True)
        meta = self.config.metadata
        entry_points = meta.entry_points
        if entry_points:
            with _open_for_write(dist_info / "entry_points.txt") as f:
                self._write_entry_points(f, entry_points)

        with _open_for_write(dist_info / "WHEEL") as f:
            self._write_wheel_file(f, is_purelib=self.config.build_config.is_purelib)

        with _open_for_write(dist_info / "METADATA") as f:
            f.write(self.format_pkginfo())

        for file in self.find_license_files():
            target = dist_info / "licenses" / file
            target.parent.mkdir(0o700, parents=True, exist_ok=True)
            shutil.copy2(self.location / file, target)
        return dist_info

    def _add_file_to_zip(
        self, zf: zipfile.ZipFile, rel_path: str, full_path: Path
    ) -> RecordEntry:

        self._show_add_file(rel_path, full_path)
        zi = zipfile.ZipInfo(rel_path, ZIPINFO_DEFAULT_DATE_TIME)
        st_mode = os.stat(full_path).st_mode
        zi.external_attr = (st_mode & 0xFFFF) << 16  # Unix attributes

        if stat.S_ISDIR(st_mode):
            zi.external_attr |= 0x10  # MS-DOS directory flag

        with full_path.open("rb") as src:
            hash_digest = self._write_zip_info(zf, zi, src)
        size = zi.file_size
        return RecordEntry(rel_path, f"sha256={hash_digest}", str(size))

    @staticmethod
    def _write_zip_info(
        zf: zipfile.ZipFile, zi: zipfile.ZipInfo, src: IO[bytes]
    ) -> str:
        hashsum = hashlib.sha256()
        for buf in iter(lambda: src.read(2**16), b""):
            hashsum.update(buf)

        src.seek(0)
        zf.writestr(zi, src.read(), compress_type=zipfile.ZIP_DEFLATED)
        return urlsafe_b64encode(hashsum.digest()).decode("ascii").rstrip("=")

    def _write_record(self, zf: zipfile.ZipFile, records: list[RecordEntry]) -> None:
        zi = zipfile.ZipInfo(f"{self.dist_info_name}/RECORD", ZIPINFO_DEFAULT_DATE_TIME)
        buffer = io.BytesIO()
        text_buffer = io.TextIOWrapper(buffer, encoding="utf-8", newline="")

        writer = csv.writer(text_buffer, lineterminator="\n")
        writer.writerows(records)
        writer.writerow(RecordEntry(zi.filename, "", ""))
        text_buffer.detach()
        buffer.seek(0)
        self._show_add_file(zi.filename, Path(zi.filename))
        self._write_zip_info(zf, zi, buffer)

    def _write_wheel_file(self, fp: IO[str], is_purelib: bool) -> None:
        fp.write(WHEEL_FILE_FORMAT.format(is_purelib=is_purelib, tag=self.tag))

    def _write_entry_points(
        self, fp: IO[str], entry_points: dict[str, dict[str, str]]
    ) -> None:
        for group_name in sorted(entry_points):
            fp.write(f"[{group_name}]\n")
            for name, value in sorted(entry_points[group_name].items()):
                fp.write(f"{name} = {value}\n")

            fp.write("\n")

    def _get_metadata_files(self, context: Context) -> Iterable[tuple[str, Path]]:
        """Generate the metadata files for the wheel."""
        if context.kwargs.get("metadata_directory"):
            return self._iter_files_in_directory(context.kwargs["metadata_directory"])
        else:
            dist_info = self._write_dist_info(context.build_dir)
            return self._iter_files_in_directory(str(dist_info))

    def _iter_files_in_directory(self, path: str) -> Iterable[tuple[str, Path]]:
        for root, _, files in os.walk(path):
            relroot = os.path.relpath(root, os.path.dirname(path))
            for file in files:
                yield (os.path.join(relroot, file), Path(root) / file)
