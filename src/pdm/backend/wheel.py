from __future__ import annotations

import csv
import hashlib
import io
import os
import posixpath
import shutil
import stat
import tempfile
import time
import zipfile
from base64 import urlsafe_b64encode
from importlib.metadata import version as get_version
from pathlib import Path
from typing import IO, Any, Iterable, Mapping, NamedTuple, cast

from pdm.backend._vendor.packaging import tags
from pdm.backend._vendor.packaging.specifiers import SpecifierSet
from pdm.backend._vendor.packaging.utils import _build_tag_regex, canonicalize_name
from pdm.backend.base import Builder
from pdm.backend.hooks import Context
from pdm.backend.hooks.setuptools import SetuptoolsBuildHook
from pdm.backend.structures import FileMap
from pdm.backend.utils import (
    normalize_file_permissions,
    safe_version,
    to_filename,
)

SCHEME_NAMES = frozenset(
    ["purelib", "platlib", "include", "platinclude", "scripts", "data"]
)


WHEEL_FILE_FORMAT = """\
Wheel-Version: 1.0
Generator: pdm-backend ({version})
Root-Is-Purelib: {is_purelib}
Tag: {tag}
"""

BUILD_TAG_FORMAT = "Build: {build_number}"

# Fix the date time for reproducible builds
try:
    _env_date = time.gmtime(int(os.environ["SOURCE_DATE_EPOCH"]))[:6]
except (ValueError, KeyError):
    ZIPINFO_DATE_TIME = (2016, 1, 1, 0, 0, 0)
else:
    if _env_date[0] < 1980:
        raise ValueError("zipinfo date can't be earlier than 1980")
    ZIPINFO_DATE_TIME = _env_date


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
        self.__build_number: str | None = None

    def scheme_path(self, name: str, relative: str) -> str:
        if name not in SCHEME_NAMES:
            raise ValueError(
                f"Unknown scheme name {name!r}, must be one of {SCHEME_NAMES}"
            )
        return f"{self.name_version}.data/{name}/{relative}"

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
        if "--plat-name" in self.config_settings:
            plat_name = self.config_settings["--plat-name"]
        return python_tag, py_limited_api, plat_name

    def prepare_metadata(self, metadata_directory: str) -> Path:
        """Write the dist-info files under the given directory"""
        context = self.build_context(Path(metadata_directory))
        self.initialize(context)
        return self._write_dist_info(Path(metadata_directory))

    def _collect_files(self, context: Context) -> FileMap:
        package_dir = self.config.build_config.package_dir
        result = FileMap()

        def clean_prefix(relpath: str) -> str:
            # remove the package-dir part from the relative paths
            if package_dir and relpath.startswith(package_dir + "/"):
                relpath = relpath[len(package_dir) + 1 :]
            return relpath

        result.update(
            (clean_prefix(k), v) for k, v in super()._collect_files(context).items()
        )
        return result

    def get_files(self, context: Context) -> Iterable[tuple[str, Path]]:
        yield from super().get_files(context)
        yield from self._get_metadata_files(context)
        yield from self._get_wheel_data(context)

    def _get_wheel_data(self, context: Context) -> Iterable[tuple[str, Path]]:
        for name, paths in context.config.build_config.wheel_data.items():
            for path in paths:
                relative_to: Path | None = None
                if not isinstance(path, str):
                    if path.get("relative-to"):
                        relative_to = context.root / path["relative-to"]
                    path = path["path"]
                for child in context.expand_paths(path):
                    relpath = (
                        child.relative_to(relative_to).as_posix()
                        if relative_to
                        else child.name
                    )
                    yield self.scheme_path(name, relpath), child

    def build_artifact(
        self, context: Context, files: Iterable[tuple[str, Path]]
    ) -> Path:
        records: list[RecordEntry] = []
        fd, temp_name = tempfile.mkstemp(suffix=".whl")
        st_mode = os.stat(temp_name).st_mode
        new_mode = normalize_file_permissions(st_mode)
        os.chmod(temp_name, new_mode)

        with os.fdopen(fd, "w+b") as fp:
            with zipfile.ZipFile(fp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for rel_path, full_path in files:
                    records.append(self._add_file_to_zip(zf, rel_path, full_path))
                self._write_record(zf, records)

        name_version = self.name_version
        if self.build_number:
            name_version = f"{name_version}-{self.build_number}"

        target = context.dist_dir / f"{name_version}-{self.tag}.whl"
        if target.exists():
            target.unlink()
        shutil.move(temp_name, target)
        return target

    @property
    def name_version(self) -> str:
        name = to_filename(canonicalize_name(self.config.metadata["name"]))
        version = to_filename(safe_version(self.config.metadata["version"]))
        return f"{name}-{version}"

    @property
    def build_number(self) -> str | None:
        if not self.__build_number:
            self.__build_number = self._get_build_number()
        return self.__build_number

    @property
    def dist_info_name(self) -> str:
        return f"{self.name_version}.dist-info"

    @property
    def tag(self) -> str:
        if self.__tag is None:
            self.__tag = self._get_tag()
        return self.__tag

    def _get_build_number(self) -> str | None:
        cmd = "--build-number"
        if cmd not in self.config_settings:
            return None
        build_number = self.config_settings[cmd]
        if not _build_tag_regex.match(build_number):
            raise ValueError(
                f"Invalid build number: {build_number}, please refer to PEP 427"
            )

        return build_number

    def _get_tag(self) -> str:
        impl, abi, platform = self._get_platform_tags()
        is_purelib = self.config.build_config.is_purelib
        if not is_purelib:
            sys_tag = next(tags.sys_tags())
            if not platform:
                platform = sys_tag.platform
            if not impl:
                impl = sys_tag.interpreter
            if not abi:
                abi = sys_tag.abi
        else:
            if not platform:
                platform = "any"
            if not abi:
                abi = "none"
            if not impl:
                requires_python = self.config.metadata.get("requires-python", "")
                if SpecifierSet(requires_python).contains("2.7"):
                    impl = "py2.py3"
                else:
                    impl = "py3"

        platform = platform.lower().replace("-", "_").replace(".", "_")  # type: ignore
        tag = (impl, abi, platform)
        return "-".join(tag)  # type: ignore[arg-type]

    def _write_dist_info(self, parent: Path) -> Path:
        """write the dist-info directory and return the path to it"""
        dist_info = parent / self.dist_info_name
        dist_info.mkdir(0o700, exist_ok=True)
        meta = self.config.validate()
        entry_points = meta.entrypoints.copy()
        entry_points.update(
            {"console_scripts": meta.scripts, "gui_scripts": meta.gui_scripts}
        )
        if entry_points:
            with _open_for_write(dist_info / "entry_points.txt") as f:
                self._write_entry_points(f, entry_points)

        with _open_for_write(dist_info / "WHEEL") as f:
            self._write_wheel_file(f, is_purelib=self.config.build_config.is_purelib)

        with _open_for_write(dist_info / "METADATA") as f:
            f.write(str(meta.as_rfc822()))

        for file in self.find_license_files(meta):
            target = dist_info / "licenses" / file
            target.parent.mkdir(0o700, parents=True, exist_ok=True)
            shutil.copy2(self.location / file, target)
        return dist_info

    def _add_file_to_zip(
        self, zf: zipfile.ZipFile, rel_path: str, full_path: Path
    ) -> RecordEntry:
        self._show_add_file(rel_path, full_path)
        zi = zipfile.ZipInfo(rel_path, ZIPINFO_DATE_TIME)
        st_mode = full_path.stat().st_mode
        new_mode = normalize_file_permissions(st_mode)
        zi.external_attr = (new_mode & 0xFFFF) << 16  # Unix attributes

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
        data = src.read()
        hashsum.update(data)
        zf.writestr(zi, data, compress_type=zipfile.ZIP_DEFLATED)
        return urlsafe_b64encode(hashsum.digest()).decode("ascii").rstrip("=")

    def _write_record(self, zf: zipfile.ZipFile, records: list[RecordEntry]) -> None:
        zi = zipfile.ZipInfo(f"{self.dist_info_name}/RECORD", ZIPINFO_DATE_TIME)
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
        try:
            version = get_version("pdm-backend")
        except ModuleNotFoundError:
            version = "0.0.0+local"

        wheel_metadata = WHEEL_FILE_FORMAT.format(
            is_purelib=str(is_purelib).lower(), tag=self.tag, version=version
        )

        if self.build_number:
            wheel_metadata = f"{wheel_metadata}{BUILD_TAG_FORMAT.format(build_number=self.build_number)}"

        fp.write(wheel_metadata)

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
            return self._iter_metadata_files(context.kwargs["metadata_directory"])
        else:
            dist_info = self._write_dist_info(context.ensure_build_dir())
            return self._iter_metadata_files(str(dist_info))

    def _iter_metadata_files(self, path: str) -> Iterable[tuple[str, Path]]:
        dist_info_name = self.dist_info_name
        for root, _, files in os.walk(path):
            for file in files:
                # the relative path is concated with the dist-info name
                # so that the dist info name is always consistent with the current build
                # e.g. <path>/METADATA -> <name>-<version>.dist-info/METADATA
                relpath = posixpath.join(
                    dist_info_name, Path(root, file).relative_to(path).as_posix()
                )
                yield relpath, Path(root, file)
