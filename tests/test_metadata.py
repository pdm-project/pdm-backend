import subprocess
from datetime import datetime

import pytest

from pdm.pep517.metadata import Metadata
from tests import FIXTURES


def test_parse_module() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-module/pyproject.toml")
    assert metadata.name == "demo-module"
    assert metadata.version == "0.1.0"
    assert metadata.author == ""
    assert metadata.author_email == "frostming <mianghong@gmail.com>"
    paths = metadata.convert_package_paths()
    assert sorted(paths["py_modules"]) == ["bar_module", "foo_module"]
    assert paths["packages"] == []
    assert paths["package_dir"] == {}


def test_parse_package() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-package-include/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["py_modules"] == []
    assert paths["packages"] == ["my_package"]
    assert paths["package_dir"] == {}
    assert paths["package_data"] == {"": ["*"]}
    assert not metadata.classifiers


def test_package_with_old_include() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-package-include-old/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["py_modules"] == []
    assert paths["packages"] == ["my_package"]
    assert paths["package_dir"] == {}
    assert paths["package_data"] == {"": ["*"]}
    assert not metadata.classifiers


def test_parse_error_package() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-package-include-error/pyproject.toml")
    with pytest.raises(ValueError):
        metadata.convert_package_paths()


def test_parse_src_package() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-src-package/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["packages"] == ["my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {"": "src"}


def test_parse_pep420_namespace_package() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-pep420-package/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["package_dir"] == {}
    assert paths["packages"] == ["foo.my_package"]
    assert paths["py_modules"] == []


def test_parse_package_with_extras() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-combined-extras/pyproject.toml")
    assert metadata.dependencies == ["urllib3"]
    assert metadata.optional_dependencies == {
        "be": ["idna"],
        "te": ["chardet"],
        "all": ["idna", "chardet"],
    }
    assert metadata.requires_extra == {
        "be": ['idna; extra == "be"'],
        "te": ['chardet; extra == "te"'],
        "all": ['idna; extra == "all"', 'chardet; extra == "all"'],
    }


def test_project_version_use_scm(project_with_scm) -> None:
    metadata = Metadata(project_with_scm / "pyproject.toml")
    assert metadata.version == "0.1.0"
    project_with_scm.joinpath("test.txt").write_text("hello\n")
    subprocess.check_call(["git", "add", "test.txt"])
    date = datetime.utcnow().strftime("%Y%m%d")
    assert metadata.version == f"0.1.0+d{date}"
    subprocess.check_call(["git", "commit", "-m", "add test.txt"])
    assert "0.1.1.dev1+g" in metadata.version


def test_project_name_and_version_missing() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-no-name-nor-version/pyproject.toml")
    assert metadata.version is None
    assert metadata.name is None
    assert metadata.project_name is None
    assert metadata.project_filename == "UNKNOWN"


def test_explicit_package_dir() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-explicit-package-dir/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["packages"] == ["my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {"": "foo"}


def test_implicit_namespace_package() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-pep420-package/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["packages"] == ["foo.my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {}


def test_src_dir_containing_modules() -> None:
    metadata = Metadata(FIXTURES / "projects/demo-src-pymodule/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["package_dir"] == {"": "src"}
    assert not paths["packages"]
    assert paths["py_modules"] == ["foo_module"]
