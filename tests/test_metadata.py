import pytest

from pdm.backend.config import Config
from tests import FIXTURES


def test_parse_module(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-module")
    monkeypatch.chdir(metadata.root)
    paths = metadata.convert_package_paths()
    assert sorted(paths["py_modules"]) == ["bar_module", "foo_module"]
    assert paths["packages"] == []
    assert paths["package_dir"] == {}


def test_parse_package(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-package-include")
    monkeypatch.chdir(metadata.root)
    paths = metadata.convert_package_paths()
    assert paths["py_modules"] == []
    assert paths["packages"] == ["my_package"]
    assert paths["package_dir"] == {}
    assert paths["package_data"] == {"": ["*"]}


def test_parse_error_package(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-package-include-error")
    monkeypatch.chdir(metadata.root)
    with pytest.raises(ValueError):
        metadata.convert_package_paths()


def test_parse_src_package(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-src-package")
    monkeypatch.chdir(metadata.root)
    paths = metadata.convert_package_paths()
    assert paths["packages"] == ["my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {"": "src"}


def test_parse_pep420_namespace_package(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-pep420-package")
    monkeypatch.chdir(metadata.root)
    paths = metadata.convert_package_paths()
    assert paths["package_dir"] == {}
    assert paths["packages"] == ["foo.my_package"]
    assert paths["py_modules"] == []


def test_explicit_package_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-explicit-package-dir")
    monkeypatch.chdir(metadata.root)
    paths = metadata.convert_package_paths()
    assert paths["packages"] == ["my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {"": "foo"}


def test_implicit_namespace_package(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-pep420-package")
    monkeypatch.chdir(metadata.root)
    paths = metadata.convert_package_paths()
    assert paths["packages"] == ["foo.my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {}


def test_src_dir_containing_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = Config.from_pyproject(FIXTURES / "projects/demo-src-pymodule")
    monkeypatch.chdir(metadata.root)
    paths = metadata.convert_package_paths()
    assert paths["package_dir"] == {"": "src"}
    assert not paths["packages"]
    assert paths["py_modules"] == ["foo_module"]
