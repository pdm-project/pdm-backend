import subprocess
from datetime import datetime
from typing import Optional

import pytest

from pdm.pep517.metadata import Metadata
from tests import FIXTURES


def make_metadata(data: dict, tool_settings: Optional[dict] = None) -> Metadata:
    metadata = Metadata("fake-path", parse=False)
    metadata._metadata = data
    if tool_settings:
        metadata._tool_settings = tool_settings
    return metadata


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


def test_project_version_use_scm_from_env(project_with_scm, monkeypatch) -> None:
    monkeypatch.setenv("PDM_PEP517_SCM_VERSION", "1.0.0")
    metadata = Metadata(project_with_scm / "pyproject.toml")
    assert metadata.version == "1.0.0"


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


def test_metadata_name_missing() -> None:
    metadata = make_metadata({"description": "test package", "version": "0.1.0"})
    with pytest.raises(ValueError, match="name: must be given"):
        metadata.name


def test_metadata_version_in_tool_but_not_dynamic() -> None:
    metadata = make_metadata(
        {"description": "test package", "name": "demo"}, {"version": {"use_scm": True}}
    )
    with pytest.raises(ValueError, match="version: missing from 'dynamic'"):
        metadata.version


@pytest.mark.deprecation
def test_license_classifiers_warning(recwarn) -> None:
    metadata = make_metadata(
        {
            "description": "test package",
            "name": "demo",
            "version": "0.1.0",
            "classifiers": ["License :: OSI Approved :: MIT License"],
        }
    )
    metadata.classifiers
    assert len(recwarn) == 1
    assert str(recwarn.pop(UserWarning).message).startswith(
        "License classifiers are deprecated"
    )


def test_both_license_and_license_expression_error() -> None:
    metadata = make_metadata(
        {
            "description": "test package",
            "name": "demo",
            "version": "0.1.0",
            "license": {"text": "MIT"},
            "license-expression": "MIT",
        }
    )
    with pytest.raises(
        ValueError,
        match="license-expression: Can't specify both 'license' and "
        "'license-expression' fields",
    ):
        metadata.license_expression


@pytest.mark.deprecation
@pytest.mark.xfail(reason="Don't emit warning until PEP 639 is accepted")
def test_deprecated_license_field_warning(recwarn) -> None:
    metadata = make_metadata(
        {
            "description": "test package",
            "name": "demo",
            "version": "0.1.0",
            "license": {"text": "MIT"},
        }
    )
    assert metadata.license_expression == "MIT"
    assert len(recwarn) == 1
    assert str(recwarn.pop(UserWarning).message).startswith(
        "'license' field is deprecated"
    )


def test_missing_license_expression_warning(recwarn) -> None:
    metadata = make_metadata(
        {
            "description": "test package",
            "name": "demo",
            "version": "0.1.0",
        }
    )
    assert not metadata.license_expression
    assert len(recwarn) == 1
    assert str(recwarn.pop(UserWarning).message).startswith(
        "'license-expression' is missing"
    )


@pytest.mark.deprecation
@pytest.mark.xfail(reason="Don't emit warning until PEP 639 is accepted")
def test_deprecated_license_file_warning(recwarn) -> None:
    metadata = make_metadata(
        {
            "description": "test package",
            "name": "demo",
            "version": "0.1.0",
            "license-expression": "MIT",
            "license": {"file": "LICENSE"},
        }
    )
    assert metadata.license_files == {"paths": ["LICENSE"]}
    assert len(recwarn) == 1
    assert str(recwarn.pop(UserWarning).message).startswith(
        "'license.file' field is deprecated"
    )


def test_default_license_files() -> None:
    metadata = make_metadata(
        {
            "description": "test package",
            "name": "demo",
            "version": "0.1.0",
            "license-expression": "MIT",
        }
    )
    assert metadata.license_files == {
        "globs": ["LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*"]
    }


def test_license_normalization() -> None:
    metadata = make_metadata(
        {
            "description": "test package",
            "name": "demo",
            "version": "0.1.0",
            "license-expression": "mIt",
        }
    )
    with pytest.warns(UserWarning) as record:
        assert metadata.license_expression == "MIT"

    assert len(record) == 1
    assert str(record.pop(UserWarning).message).startswith(
        "License expression normalized to"
    )


def test_invalid_license_identifier() -> None:
    metadata = make_metadata(
        {
            "description": "test package",
            "name": "demo",
            "version": "0.1.0",
            "license-expression": "foo OR MIT",
        }
    )
    with pytest.raises(ValueError, match=r".*Unknown license key\(s\): foo"):
        metadata.license_expression
