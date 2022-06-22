import contextlib
import csv
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tokenize
import zipfile
from base64 import urlsafe_b64encode
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Generator, List, Mapping, Optional, TextIO, Tuple, Union

from pdm.pep517 import __version__
from pdm.pep517._vendor.packaging import tags
from pdm.pep517._vendor.packaging.specifiers import SpecifierSet
from pdm.pep517.base import Builder
from pdm.pep517.exceptions import BuildError, PDMWarning
from pdm.pep517.utils import get_abi_tag, get_platform, show_warning

WHEEL_FILE_FORMAT = (
    """\
Wheel-Version: 1.0
Generator: pdm-pep517 %s
Root-Is-Purelib: {is_purelib}
Tag: {tag}
"""
    % __version__
)

PY_LIMITED_API_PATTERN = r"cp3\d"


class WheelBuilder(Builder):
    def __init__(
        self,
        location: Union[str, Path],
        config_settings: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(location, config_settings)
        self._records = []  # type: List[Tuple[str, str, str]]
        self._parse_config_settings()

    def _parse_config_settings(self) -> None:
        self.python_tag = None
        self.py_limited_api = None
        self.plat_name = None
        if not self.config_settings:
            return
        if "--python-tag" in self.config_settings:
            self.python_tag = self.config_settings["--python-tag"]
        if "--py-limited-api" in self.config_settings:
            self.py_limited_api = self.config_settings["--py-limited-api"]
            if not re.match(PY_LIMITED_API_PATTERN, self.py_limited_api):
                raise ValueError(
                    "py-limited-api must match '%s'" % PY_LIMITED_API_PATTERN
                )
        if "--plat-name" in self.config_settings:
            self.plat_name = self.config_settings["--plat-name"]

    def build(self, build_dir: str, **kwargs: Any) -> str:
        if not os.path.exists(build_dir):
            os.makedirs(build_dir, exist_ok=True)

        self._records.clear()
        fd, temp_path = tempfile.mkstemp(suffix=".whl")
        os.close(fd)

        with zipfile.ZipFile(
            temp_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            self._copy_module(zip_file)
            self._build(zip_file)
            self._write_metadata(zip_file)

        target = os.path.join(build_dir, self.wheel_filename)
        if os.path.exists(target):
            os.unlink(target)
        shutil.move(temp_path, target)

        return target

    @property
    def wheel_filename(self) -> str:
        name = self.meta.project_filename
        version = self.meta_version
        return f"{name}-{version}-{self.tag}.whl"

    @property
    def tag(self) -> str:
        platform = self.plat_name
        impl = self.python_tag
        if not self.meta.config.is_purelib:
            if not platform:
                platform = get_platform(self.location / "build")
            if not impl:
                impl = tags.interpreter_name() + tags.interpreter_version()
            if self.py_limited_api and impl.startswith("cp3"):
                impl = self.py_limited_api
                abi_tag = "abi3"
            else:
                abi_tag = str(get_abi_tag()).lower()
        else:
            if not platform:
                platform = "any"
            abi_tag = "none"
            if not impl:
                if self.meta.requires_python and SpecifierSet(
                    self.meta.requires_python
                ).contains("2.7"):
                    impl = "py2.py3"
                else:
                    impl = "py3"

        platform = platform.lower().replace("-", "_").replace(".", "_")
        tag = (impl, abi_tag, platform)
        if not self.meta.config.is_purelib:
            supported_tags = [(t.interpreter, t.abi, platform) for t in tags.sys_tags()]
            assert (
                tag in supported_tags
            ), f"would build wheel with unsupported tag {tag}"
        return "-".join(tag)

    @property
    def dist_info_name(self) -> str:
        name = self.meta.project_filename
        version = self.meta_version
        return f"{name}-{version}.dist-info"

    def _write_record(self, fp: TextIO) -> None:
        writer = csv.writer(fp, lineterminator="\n")
        writer.writerows(
            [(path, f"sha256={hash}", size) for path, hash, size in self._records]
        )
        writer.writerow([self.dist_info_name + "/RECORD", "", ""])

    def _write_metadata(self, wheel: zipfile.ZipFile) -> None:
        dist_info = self.dist_info_name
        if self.meta.entry_points:
            with self._write_to_zip(wheel, dist_info + "/entry_points.txt") as f:
                self._write_entry_points(f)

        with self._write_to_zip(wheel, dist_info + "/WHEEL") as f:
            self._write_wheel_file(f)

        with self._write_to_zip(wheel, dist_info + "/METADATA") as f:
            self._write_metadata_file(f)

        for license_file in self.find_license_files():
            self._add_file(
                wheel,
                os.path.join(self.location, license_file),
                f"{dist_info}/license_files/{license_file}",
            )

        with self._write_to_zip(wheel, dist_info + "/RECORD") as f:
            self._write_record(f)

    @contextlib.contextmanager
    def _write_to_zip(
        self, wheel: zipfile.ZipFile, rel_path: str
    ) -> Generator[StringIO, None, None]:
        sio = StringIO()
        yield sio

        # The default is a fixed timestamp rather than the current time, so
        # that building a wheel twice on the same computer can automatically
        # give you the exact same result.
        date_time = (2016, 1, 1, 0, 0, 0)
        zi = zipfile.ZipInfo(rel_path, date_time)
        b = sio.getvalue().encode("utf-8")
        hashsum = hashlib.sha256(b)
        hash_digest = urlsafe_b64encode(hashsum.digest()).decode("ascii").rstrip("=")

        wheel.writestr(zi, b, compress_type=zipfile.ZIP_DEFLATED)
        print(f" - Adding {rel_path}")
        self._records.append((rel_path, hash_digest, str(len(b))))

    def _build(self, wheel: zipfile.ZipFile) -> None:
        build_dir = self.location / "build"
        if build_dir.exists():
            shutil.rmtree(str(build_dir))
        lib_dir: Optional[Path] = None
        if self.meta.config.setup_script:
            if self.meta.config.run_setuptools:
                setup_py = self.ensure_setup_py()
                build_args = [
                    sys.executable,
                    str(setup_py),
                    "build",
                    "-b",
                    str(build_dir),
                ]
                try:
                    subprocess.check_call(build_args)
                except subprocess.CalledProcessError as e:
                    raise BuildError(f"Error occurs when running {build_args}:\n{e}")
                lib_dir = next(build_dir.glob("lib.*"), None)
            else:
                build_dir.mkdir(exist_ok=True)
                with tokenize.open(self.meta.config.setup_script) as f:
                    code = compile(f.read(), self.meta.config.setup_script, "exec")
                global_dict: Dict[str, Any] = {}
                exec(code, global_dict)
                if "build" not in global_dict:
                    show_warning(
                        "No build() function found in the setup script, do nothing",
                        PDMWarning,
                    )
                    return
                global_dict["build"](str(self.location), str(build_dir))
                lib_dir = build_dir
        if lib_dir is None:
            lib_dir = build_dir
        if not lib_dir.exists():
            lib_dir.mkdir(parents=True)
        self._write_version(lib_dir)

        _, excludes = self._get_include_and_exclude_paths(for_sdist=False)
        for pkg in lib_dir.glob("**/*"):
            if pkg.is_dir():
                continue

            whl_path = rel_path = pkg.relative_to(lib_dir).as_posix()
            if self.meta.config.package_dir:
                # act like being in the package_dir
                rel_path = os.path.join(self.meta.config.package_dir, rel_path)

            if self._is_excluded(rel_path, excludes):
                continue

            if whl_path in wheel.namelist():
                continue

            self._add_file(wheel, pkg.as_posix(), whl_path)

    def _write_version(self, destination: Path) -> None:
        dynamic_version = self.meta.config.dynamic_version
        if (
            not dynamic_version
            or dynamic_version.source != "scm"
            or "write_to" not in dynamic_version.options
        ):
            return
        write_template = dynamic_version.options.get("write_template", "{}\n")
        write_to = dynamic_version.options["write_to"]
        write_path = destination / write_to
        write_path.parent.mkdir(parents=True, exist_ok=True)
        with write_path.open("w") as f:
            f.write(write_template.format(self.meta_version))

    def _copy_module(self, wheel: zipfile.ZipFile) -> None:
        for path in self.find_files_to_add():
            rel_path = None
            if self.meta.config.package_dir:
                try:
                    rel_path = path.relative_to(self.meta.config.package_dir).as_posix()
                except ValueError:
                    pass
            self._add_file(wheel, str(path), rel_path)

    def _add_file(
        self, wheel: zipfile.ZipFile, full_path: str, rel_path: Optional[str] = None
    ) -> None:
        if not rel_path:
            rel_path = full_path
        if os.sep != "/":
            # We always want to have /-separated paths in the zip file and in RECORD
            rel_path = rel_path.replace(os.sep, "/")
        print(f" - Adding {rel_path}")
        zinfo = zipfile.ZipInfo.from_file(full_path, rel_path)

        # Normalize permission bits to either 755 (executable) or 644
        st_mode = os.stat(full_path).st_mode

        if stat.S_ISDIR(st_mode):
            zinfo.external_attr |= 0x10  # MS-DOS directory flag

        hashsum = hashlib.sha256()
        with open(full_path, "rb") as src:
            while True:
                buf = src.read(1024 * 8)
                if not buf:
                    break
                hashsum.update(buf)

            src.seek(0)
            wheel.writestr(zinfo, src.read(), compress_type=zipfile.ZIP_DEFLATED)

        size = os.stat(full_path).st_size
        hash_digest = urlsafe_b64encode(hashsum.digest()).decode("ascii").rstrip("=")

        self._records.append((rel_path, hash_digest, str(size)))

    def _write_metadata_file(self, fp: TextIO) -> None:
        fp.write(self.format_pkginfo())

    def _write_wheel_file(self, fp: TextIO) -> None:
        fp.write(
            WHEEL_FILE_FORMAT.format(
                is_purelib=self.meta.config.is_purelib, tag=self.tag
            )
        )

    def _write_entry_points(self, fp: TextIO) -> None:
        entry_points = self.meta.entry_points
        for group_name in sorted(entry_points):
            fp.write(f"[{group_name}]\n")
            for ep in sorted(entry_points[group_name]):
                fp.write(ep.replace(" ", "") + "\n")

            fp.write("\n")
