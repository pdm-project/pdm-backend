import email
import sys
import zipfile
from pathlib import Path

import pytest

from pdm.pep517 import api
from tests.testutils import build_fixture_project, get_tarball_names, get_wheel_names


def test_build_single_module(tmp_path: Path) -> None:
    with build_fixture_project("demo-module"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert api.get_requires_for_build_sdist() == []
        assert api.get_requires_for_build_wheel() == []
        assert sdist_name == "demo-module-0.1.0.tar.gz"
        assert wheel_name == "demo_module-0.1.0-py3-none-any.whl"
        tar_names = get_tarball_names(tmp_path / sdist_name)
        for name in [
            "foo_module.py",
            "bar_module.py",
            "LICENSE",
            "pyproject.toml",
            "PKG-INFO",
            "README.md",
        ]:
            assert f"demo-module-0.1.0/{name}" in tar_names

        zip_names = get_wheel_names(tmp_path / wheel_name)
        for name in ["foo_module.py", "bar_module.py"]:
            assert name in zip_names

        for name in ("pyproject.toml", "LICENSE"):
            assert name not in zip_names

        assert "demo_module-0.1.0.dist-info/license_files/LICENSE" in zip_names


def test_build_package(tmp_path: Path) -> None:
    with build_fixture_project("demo-package"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert sdist_name == "demo-package-0.1.0.tar.gz"
        assert wheel_name == "demo_package-0.1.0-py2.py3-none-any.whl"

        tar_names = get_tarball_names(tmp_path / sdist_name)
        assert "demo-package-0.1.0/my_package/__init__.py" in tar_names
        assert "demo-package-0.1.0/my_package/data.json" in tar_names
        assert "demo-package-0.1.0/single_module.py" not in tar_names
        assert "demo-package-0.1.0/data_out.json" in tar_names

        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "my_package/__init__.py" in zip_names
        assert "my_package/data.json" in zip_names
        assert "single_module.py" not in zip_names
        assert "data_out.json" not in zip_names


def test_build_src_package(tmp_path: Path) -> None:
    with build_fixture_project("demo-src-package"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert sdist_name == "demo-package-0.1.0.tar.gz"
        assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

        tar_names = get_tarball_names(tmp_path / sdist_name)
        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "demo-package-0.1.0/src/my_package/__init__.py" in tar_names
        assert "demo-package-0.1.0/src/my_package/data.json" in tar_names

        assert "my_package/__init__.py" in zip_names
        assert "my_package/data.json" in zip_names


def test_build_package_include(tmp_path: Path) -> None:
    with build_fixture_project("demo-package-include"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert sdist_name == "demo-package-0.1.0.tar.gz"
        assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

        tar_names = get_tarball_names(tmp_path / sdist_name)
        zip_names = get_wheel_names(tmp_path / wheel_name)

        assert "demo-package-0.1.0/my_package/__init__.py" in tar_names
        assert "demo-package-0.1.0/my_package/data.json" not in tar_names
        assert "demo-package-0.1.0/requirements.txt" in tar_names
        assert "demo-package-0.1.0/data_out.json" in tar_names

        assert "my_package/__init__.py" in zip_names
        assert "my_package/data.json" not in zip_names
        assert "requirements.txt" in zip_names
        assert "data_out.json" in zip_names


def test_namespace_package_by_include(tmp_path: Path) -> None:
    with build_fixture_project("demo-pep420-package"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert sdist_name == "demo-package-0.1.0.tar.gz"
        assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

        tar_names = get_tarball_names(tmp_path / sdist_name)
        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "demo-package-0.1.0/foo/my_package/__init__.py" in tar_names
        assert "demo-package-0.1.0/foo/my_package/data.json" in tar_names

        assert "foo/my_package/__init__.py" in zip_names
        assert "foo/my_package/data.json" in zip_names


def test_build_explicit_package_dir(tmp_path: Path) -> None:
    with build_fixture_project("demo-explicit-package-dir"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert sdist_name == "demo-package-0.1.0.tar.gz"
        assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

        tar_names = get_tarball_names(tmp_path / sdist_name)
        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "demo-package-0.1.0/foo/my_package/__init__.py" in tar_names
        assert "demo-package-0.1.0/foo/my_package/data.json" in tar_names

        assert "my_package/__init__.py" in zip_names
        assert "my_package/data.json" in zip_names


def test_prepare_metadata(tmp_path: Path) -> None:
    with build_fixture_project("demo-package"):
        dist_info = api.prepare_metadata_for_build_wheel(tmp_path.as_posix())
        assert dist_info == "demo_package-0.1.0.dist-info"
        for filename in ("WHEEL", "METADATA"):
            assert (tmp_path / dist_info / filename).is_file()


def test_build_package_with_modules_in_src(tmp_path: Path) -> None:
    with build_fixture_project("demo-src-pymodule"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())

        tar_names = get_tarball_names(tmp_path / sdist_name)
        assert "demo-module-0.1.0/src/foo_module.py" in tar_names

        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "foo_module.py" in zip_names


def test_build_with_cextension(tmp_path: Path) -> None:
    with build_fixture_project("demo-cextension"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert api.get_requires_for_build_sdist() == []
        assert api.get_requires_for_build_wheel() == ["setuptools>=40.8.0"]

        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "my_package/__init__.py" in zip_names
        assert (
            "my_package/hellomodule.c" not in zip_names
        ), "Not collect c files while building wheel"

        tar_names = get_tarball_names(tmp_path / sdist_name)
        assert "demo-package-0.1.0/my_package/__init__.py" in tar_names
        assert (
            "demo-package-0.1.0/my_package/hellomodule.c" in tar_names
        ), "Collect c files while building sdist"
        assert not any(
            path.startswith("build") for path in tar_names
        ), 'Not collect c files in temporary directory "./build"'


def test_build_with_cextension_in_src(tmp_path: Path) -> None:
    with build_fixture_project("demo-cextension-in-src"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())

        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "my_package/__init__.py" in zip_names
        assert (
            "my_package/hellomodule.c" not in zip_names
        ), "Not collect c files while building wheel"

        tar_names = get_tarball_names(tmp_path / sdist_name)
        assert "demo-package-0.1.0/src/my_package/__init__.py" in tar_names
        assert (
            "demo-package-0.1.0/src/my_package/hellomodule.c" in tar_names
        ), "Collect c files while building sdist"
        assert not any(
            path.startswith("build") for path in tar_names
        ), 'Not collect c files in temporary directory "./build"'


def test_build_editable(tmp_path: Path) -> None:
    with build_fixture_project("demo-package") as project:
        wheel_name = api.build_editable(tmp_path.as_posix())
        assert api.get_requires_for_build_editable() == []
        with zipfile.ZipFile(tmp_path / wheel_name) as zf:
            namelist = zf.namelist()
            assert "demo_package.pth" in namelist
            assert "__editables_demo_package.py" in namelist
            assert "demo_package-0.1.0.dist-info/license_files/LICENSE" in namelist

            metadata = email.message_from_bytes(
                zf.read("demo_package-0.1.0.dist-info/METADATA")
            )
            assert "editables" in metadata.get_all("Requires-Dist", [])

            pth_content = zf.read("demo_package.pth").decode("utf-8").strip()
            assert pth_content == "import __editables_demo_package"

            proxy_module = (
                zf.read("__editables_demo_package.py").decode("utf-8").strip()
            )
            assert proxy_module == (
                "from editables.redirector import RedirectingFinder as F\n"
                "F.install()\n"
                "F.map_module('my_package', {!r})".format(
                    str((project / "my_package" / "__init__.py").resolve())
                )
            )


def test_build_editable_src(tmp_path: Path) -> None:
    with build_fixture_project("demo-src-package-include") as project:
        wheel_name = api.build_editable(tmp_path.as_posix())

        with zipfile.ZipFile(tmp_path / wheel_name) as zf:
            namelist = zf.namelist()
            assert "demo_package.pth" in namelist
            assert "__editables_demo_package.py" in namelist
            assert "my_package/data.json" not in namelist
            assert "data_out.json" in namelist

            pth_content = zf.read("demo_package.pth").decode("utf-8").strip()
            assert pth_content == "import __editables_demo_package"

            proxy_module = (
                zf.read("__editables_demo_package.py").decode("utf-8").strip()
            )
            assert proxy_module == (
                "from editables.redirector import RedirectingFinder as F\n"
                "F.install()\n"
                "F.map_module('my_package', {!r})".format(
                    str((project / "sub" / "my_package" / "__init__.py").resolve())
                )
            )


def test_build_editable_pep420(tmp_path: Path) -> None:
    with build_fixture_project("demo-pep420-package") as project:
        with pytest.warns(UserWarning) as recorded:
            wheel_name = api.build_editable(tmp_path.as_posix())

        assert len(recorded) == 1
        assert str(recorded.pop().message).startswith(
            "editables backend is not available"
        )

        with zipfile.ZipFile(tmp_path / wheel_name) as zf:
            namelist = zf.namelist()
            assert "demo_package.pth" in namelist
            assert "__editables_demo_package.py" not in namelist

            metadata = email.message_from_bytes(
                zf.read("demo_package-0.1.0.dist-info/METADATA")
            )
            assert "editables" not in metadata.get_all("Requires-Dist", [])

            pth_content = zf.read("demo_package.pth").decode("utf-8").strip()
            assert pth_content == str(project.resolve())


def test_prepare_metadata_for_editable(tmp_path: Path) -> None:
    with build_fixture_project("demo-package"):
        dist_info = api.prepare_metadata_for_build_editable(tmp_path.as_posix())
        assert dist_info == "demo_package-0.1.0.dist-info"
        with (tmp_path / dist_info / "METADATA").open("rb") as metadata:
            deps = email.message_from_binary_file(metadata).get_all("Requires-Dist")
        assert "editables" in deps


def test_build_purelib_project_with_build(tmp_path: Path) -> None:
    with build_fixture_project("demo-purelib-with-build"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

        with zipfile.ZipFile(tmp_path / wheel_name) as zf:
            wheel_metadata = email.message_from_bytes(
                zf.read("demo_package-0.1.0.dist-info/WHEEL")
            )
            assert wheel_metadata["Root-Is-Purelib"] == "True"


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Check file mode on Unix only"
)
def test_build_wheel_preserve_permission(tmp_path: Path) -> None:
    with build_fixture_project("demo-package"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        with zipfile.ZipFile(tmp_path / wheel_name) as zf:
            info = zf.getinfo("my_package/executable")
            filemode = info.external_attr >> 16
            assert filemode & 0o111
