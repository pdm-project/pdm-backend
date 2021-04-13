import contextlib
import tarfile
import zipfile

import pytest

from pdm.pep517 import api, utils
from tests import FIXTURES


def get_tarball_names(path):
    with tarfile.open(path, "r:gz") as tar:
        return tar.getnames()


def get_wheel_names(path):
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


@contextlib.contextmanager
def build_fixture_project(project_name):
    project = FIXTURES / "projects" / project_name
    with utils.cd(project):
        yield


def test_build_single_module(tmp_path):
    with build_fixture_project("demo-module"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
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


def test_build_package(tmp_path):
    with build_fixture_project("demo-package"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert sdist_name == "demo-package-0.1.0.tar.gz"
        assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

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


def test_build_src_package(tmp_path):
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


def test_build_package_include(tmp_path):
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


def test_namespace_package_by_include(tmp_path):
    with build_fixture_project("demo-src-package-include"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert sdist_name == "demo-package-0.1.0.tar.gz"
        assert wheel_name == "demo_package-0.1.0-py3-none-any.whl"

        tar_names = get_tarball_names(tmp_path / sdist_name)
        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "demo-package-0.1.0/sub/my_package/__init__.py" in tar_names
        assert "demo-package-0.1.0/sub/my_package/data.json" in tar_names

        assert "sub/my_package/__init__.py" in zip_names
        assert "sub/my_package/data.json" in zip_names


def test_build_explicit_package_dir(tmp_path):
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


def test_prepare_metadata(tmp_path):
    with build_fixture_project("demo-package"):
        dist_info = api.prepare_metadata_for_build_wheel(tmp_path.as_posix())
        assert dist_info == "demo_package-0.1.0.dist-info"
        for filename in ("WHEEL", "METADATA"):
            assert (tmp_path / dist_info / filename).is_file()


@pytest.mark.xfail
def test_build_legacypackage(tmp_path):
    with build_fixture_project("demo-legacy"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())
        assert sdist_name == "demo-legacy-0.1.0.tar.gz"
        assert wheel_name == "demo_legacy-0.1.0-py3-none-any.whl"

        tar_names = get_tarball_names(tmp_path / sdist_name)
        assert "demo-legacy-0.1.0/my_package/__init__.py" in tar_names
        assert "demo-legacy-0.1.0/my_package/data.json" in tar_names
        assert "demo-legacy-0.1.0/single_module.py" not in tar_names
        assert "demo-legacy-0.1.0/data_out.json" not in tar_names

        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "my_package/__init__.py" in zip_names
        assert "my_package/data.json" in zip_names
        assert "single_module.py" not in zip_names
        assert "data_out.json" not in zip_names


def test_build_package_with_modules_in_src(tmp_path):
    with build_fixture_project("demo-src-pymodule"):
        wheel_name = api.build_wheel(tmp_path.as_posix())
        sdist_name = api.build_sdist(tmp_path.as_posix())

        tar_names = get_tarball_names(tmp_path / sdist_name)
        assert "demo-module-0.1.0/src/foo_module.py" in tar_names

        zip_names = get_wheel_names(tmp_path / wheel_name)
        assert "foo_module.py" in zip_names
