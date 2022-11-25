import pytest

from pdm.backend.config import Config, Metadata
from pdm.backend.utils import cd
from tests import FIXTURES


def test_parse_module() -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-module")
    with cd(metadata.root):
        paths = metadata.convert_package_paths()
    assert sorted(paths["py_modules"]) == ["bar_module", "foo_module"]
    assert paths["packages"] == []
    assert paths["package_dir"] == {}


def test_parse_package() -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-package-include")
    with cd(metadata.root):
        paths = metadata.convert_package_paths()
    assert paths["py_modules"] == []
    assert paths["packages"] == ["my_package"]
    assert paths["package_dir"] == {}
    assert paths["package_data"] == {"": ["*"]}


def test_parse_error_package() -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-package-include-error")
    with pytest.raises(ValueError), cd(metadata.root):
        metadata.convert_package_paths()


def test_parse_src_package() -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-src-package")
    with cd(metadata.root):
        paths = metadata.convert_package_paths()
    assert paths["packages"] == ["my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {"": "src"}


def test_parse_pep420_namespace_package() -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-pep420-package")
    with cd(metadata.root):
        paths = metadata.convert_package_paths()
    assert paths["package_dir"] == {}
    assert paths["packages"] == ["foo.my_package"]
    assert paths["py_modules"] == []


def test_explicit_package_dir() -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-explicit-package-dir")
    with cd(metadata.root):
        paths = metadata.convert_package_paths()
    assert paths["packages"] == ["my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {"": "foo"}


def test_implicit_namespace_package() -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-pep420-package")
    with cd(metadata.root):
        paths = metadata.convert_package_paths()
    assert paths["packages"] == ["foo.my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {}


def test_src_dir_containing_modules() -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-src-pymodule")
    with cd(metadata.root):
        paths = metadata.convert_package_paths()
    assert paths["package_dir"] == {"": "src"}
    assert not paths["packages"]
    assert paths["py_modules"] == ["foo_module"]


def test_default_license_files() -> None:
    metadata = Metadata(
        {
            "description": "test package",
            "name": "demo",
            "version": "0.1.0",
            "license": "MIT",
        }
    )
    assert metadata.license_files == {
        "globs": ["LICENSES/*", "LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*"]
    }
