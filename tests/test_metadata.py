import subprocess
from datetime import datetime

import pytest

from pdm.pep517.metadata import Metadata
from tests import FIXTURES


def test_parse_module():
    metadata = Metadata(FIXTURES / "projects/demo-module/pyproject.toml")
    assert metadata.name == "demo-module"
    assert metadata.version == "0.1.0"
    assert metadata.author == ""
    assert metadata.author_email == "frostming <mianghong@gmail.com>"
    paths = metadata.convert_package_paths()
    assert sorted(paths["py_modules"]) == ["bar_module", "foo_module"]
    assert paths["packages"] == []
    assert paths["package_dir"] == {}


@pytest.mark.parametrize(
    "requires_python, expect",
    [
        (
            ">=2.7",
            [
                "2",
                "2.7",
                "3",
                "3.1",
                "3.2",
                "3.3",
                "3.4",
                "3.5",
                "3.6",
                "3.7",
                "3.8",
                "3.9",
            ],
        ),
        (">=3.5", ["3", "3.5", "3.6", "3.7", "3.8", "3.9"]),
        ("<3.8,>=3.5", ["3", "3.5", "3.6", "3.7"]),
        (">=3.6.1,<3.10", ["3", "3.6", "3.7", "3.8", "3.9"]),
        (">=3.6,!=3.8,<3.10", ["3", "3.6", "3.8", "3.7", "3.9"]),  # !=3.8 means !=3.8.0
        (">=3.6,!=3.8.*,<3.10", ["3", "3.6", "3.7", "3.9"]),
        (">3.8,!=3.9.*", ["3", "3.8"]),
        (">3.9.1", ["3", "3.9"]),
        (">3.4.10,<3.5", []),  # no versions in 3.4 are larger than 3.4.10
        (">3.9.1,<3.9.1", []),
        (">3.9.1,<3.9.2", []),
        ("~=3.6", ["3", "3.6", "3.7", "3.8", "3.9"]),
        ("~=3.6.1", ["3", "3.6"]),
        ("==3.6.1", ["3", "3.6"]),
        ("===3.6.1", ["3", "3.6"]),
        # unavailable Python version does not generate classifiers
        ("==3", ["3"]),  # ==3.0 exists
        ("==2", []),  # ==2.0 not exists
    ],  # it only needs to work on released version "(?P<release>[0-9]+(?:\.[0-9]+)*)"
)
def test_autogen_classifiers(requires_python, expect):
    metadata = Metadata(FIXTURES / "projects/demo-module/pyproject.toml")
    metadata._metadata["requires-python"] = requires_python
    classifiers = metadata.classifiers
    expect_classifiers = [
        f"Programming Language :: Python :: {python_version}"
        for python_version in expect
    ]
    assert sorted(
        [
            classifier
            for classifier in classifiers
            if "Programming Language :: Python :: " in classifier
        ]
    ) == sorted(expect_classifiers)
    assert "License :: OSI Approved :: MIT License" in classifiers


def test_parse_package():
    metadata = Metadata(FIXTURES / "projects/demo-package-include/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["py_modules"] == []
    assert paths["packages"] == ["my_package"]
    assert paths["package_dir"] == {}
    assert paths["package_data"] == {"": ["*"]}
    assert not metadata.classifiers


def test_package_with_old_include():
    metadata = Metadata(FIXTURES / "projects/demo-package-include-old/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["py_modules"] == []
    assert paths["packages"] == ["my_package"]
    assert paths["package_dir"] == {}
    assert paths["package_data"] == {"": ["*"]}
    assert not metadata.classifiers


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


def test_parse_pep420_namespace_package():
    metadata = Metadata(FIXTURES / "projects/demo-pep420-package/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["package_dir"] == {}
    assert paths["packages"] == ["foo.my_package"]
    assert paths["py_modules"] == []


def test_parse_package_with_extras():
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


def test_project_version_use_scm(project_with_scm):
    metadata = Metadata(project_with_scm / "pyproject.toml")
    assert metadata.version == "0.1.0"
    project_with_scm.joinpath("test.txt").write_text("hello\n")
    subprocess.check_call(["git", "add", "test.txt"])
    date = datetime.utcnow().strftime("%Y%m%d")
    assert metadata.version == f"0.1.0+d{date}"
    subprocess.check_call(["git", "commit", "-m", "add test.txt"])
    assert "0.1.1.dev1+g" in metadata.version


def test_project_name_and_version_missing():
    metadata = Metadata(FIXTURES / "projects/demo-no-name-nor-version/pyproject.toml")
    assert metadata.version is None
    assert metadata.name is None
    assert metadata.project_name == "demo-no-name-nor-version"


def test_explicit_package_dir():
    metadata = Metadata(FIXTURES / "projects/demo-explicit-package-dir/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["packages"] == ["my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {"": "foo"}


def test_implicit_namespace_package():
    metadata = Metadata(FIXTURES / "projects/demo-pep420-package/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["packages"] == ["foo.my_package"]
    assert paths["py_modules"] == []
    assert paths["package_dir"] == {}


def test_src_dir_containing_modules():
    metadata = Metadata(FIXTURES / "projects/demo-src-pymodule/pyproject.toml")
    paths = metadata.convert_package_paths()
    assert paths["package_dir"] == {"": "src"}
    assert not paths["packages"]
    assert paths["py_modules"] == ["foo_module"]
