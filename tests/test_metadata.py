import pytest

from pdm.pep517.metadata import Metadata
from tests import FIXTURES


def test_parse_module():
    metadata = Metadata(FIXTURES / "projects/demo-module/pyproject.toml")
    assert metadata.name == "demo-module"
    assert metadata.version == "0.1.0"
    assert metadata.author == "frostming"
    assert metadata.author_email == "mianghong@gmail.com"
    paths = metadata.convert_package_paths()
    assert sorted(paths["py_modules"]) == ["bar_module", "foo_module"]
    assert paths["packages"] == []
    assert paths["package_dir"] == {}


def test_parse_package():
    metadata = Metadata(FIXTURES / "projects/demo-package-include/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["py_modules"] == []
    assert paths["packages"] == ["my_package"]
    assert paths["package_dir"] == {}
    assert paths["package_data"] == {"": ["*"]}


def test_parse_error_package():
    metadata = Metadata(FIXTURES / "projects/demo-package-include-error/pyproject.toml")
    with pytest.raises(ValueError):
        metadata.convert_package_paths()


def test_parse_src_package():
    metadata = Metadata(FIXTURES / "projects/demo-src-package/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["packages"] == ["my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {"": "src"}


def test_parse_src_package_by_include():
    metadata = Metadata(FIXTURES / "projects/demo-src-package-include/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["package_dir"] == {"": "sub"}
    assert paths["packages"] == ["my_package"]
    assert paths["py_modules"] == []


def test_parse_package_with_extras():
    metadata = Metadata(FIXTURES / "projects/demo-combined-extras/pyproject.toml")
    assert metadata.install_requires == ["urllib3"]
    assert metadata.extras_require == {"be": ["idna"], "all": ["idna", "chardet"]}
    assert metadata.requires_extra == {
        "be": ["idna; extra == 'be'"],
        "all": ["idna; extra == 'all'", "chardet; extra == 'all'"],
    }
