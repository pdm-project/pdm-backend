from pathlib import Path

import pytest

from pdm.pep517 import utils
from pdm.pep517.base import Builder, is_same_or_descendant_path
from pdm.pep517.metadata import Metadata
from tests import FIXTURES


def test_auto_include_tests_for_sdist() -> None:
    builder = Builder(FIXTURES / "projects/demo-package-with-tests")
    with utils.cd(builder.location):
        sdist_files = builder.find_files_to_add(True)
        wheel_files = builder.find_files_to_add(False)

    sdist_only_files = ("tests/__init__.py", "pyproject.toml")
    include_files = ("my_package/__init__.py",)
    for file in include_files:
        path = Path(file)
        assert path in sdist_files
        assert path in wheel_files

    for file in sdist_only_files:
        path = Path(file)
        assert path in sdist_files
        assert path not in wheel_files


@pytest.mark.parametrize(
    "target,path,expect",
    [
        ("a/b", "a", True),
        ("a/b/c", "a/b/c", True),
        ("b/c", "a", False),
        ("a", "a/b", False),
        ("a", "b/c", False),
    ],
)
def test_is_same_or_descendant_path(target, path, expect) -> None:
    assert is_same_or_descendant_path(target, path) == expect


def test_recursive_glob_patterns_in_includes() -> None:
    builder = Builder(FIXTURES / "projects/demo-package-with-deep-path")
    with builder:
        sdist_files = builder.find_files_to_add(True)
        wheel_files = builder.find_files_to_add(False)

    data_files = (
        "my_package/data/data_a.json",
        "my_package/data/data_inner/data_b.json",
    )

    assert Path("my_package/__init__.py") in sdist_files
    assert Path("my_package/__init__.py") in wheel_files

    for file in data_files:
        path = Path(file)
        assert path in sdist_files
        assert path not in wheel_files


@pytest.mark.parametrize(
    ["includes", "excludes", "data_a_exist", "data_b_exist"],
    [
        (["**/*.json"], ["my_package/data/*.json"], False, True),
        (["my_package/data/data_a.json"], ["my_package/data/*.json"], True, False),
        (
            ["my_package/", "my_package/data/data_a.json"],
            ["my_package/data/data_a.json"],
            False,
            True,
        ),
        (["my_package/data/*"], ["my_package/data/"], True, False),
        (["**/data/*.json"], ["my_package/data/*.json"], False, False),
    ],
)
def test_merge_includes_and_excludes(
    monkeypatch, includes, excludes, data_a_exist: bool, data_b_exist: bool
) -> None:
    builder = Builder(FIXTURES / "projects/demo-package-with-deep-path")
    data_a, data_b = Path("my_package/data/data_a.json"), Path(
        "my_package/data/data_inner/data_b.json"
    )
    with builder:
        monkeypatch.setattr(Metadata, "source_includes", [])
        monkeypatch.setattr(Metadata, "includes", includes)
        monkeypatch.setattr(Metadata, "excludes", excludes)
        include_files = builder.find_files_to_add()
        assert (data_a in include_files) == data_a_exist
        assert (data_b in include_files) == data_b_exist


def test_license_file_globs_no_matching() -> None:
    builder = Builder(FIXTURES / "projects/demo-no-license")
    with builder:
        with pytest.warns(UserWarning) as warns:
            license_files = builder.find_license_files()

    assert not license_files
    assert len(warns) == 1
    assert str(warns.pop(UserWarning).message).startswith(
        "No license files are matched with glob patterns"
    )


def test_license_file_paths_no_matching() -> None:
    builder = Builder(FIXTURES / "projects/demo-no-license")
    builder.meta._metadata["license-files"] = {"paths": ["LICENSE"]}
    with builder:
        with pytest.raises(ValueError, match="License files not found"):
            builder.find_license_files()


@pytest.mark.parametrize("key", ["paths", "globs"])
def test_license_file_explicit_empty(recwarn, key) -> None:
    builder = Builder(FIXTURES / "projects/demo-no-license")
    builder.meta._metadata["license-files"] = {key: []}
    with builder:
        license_files = builder.find_license_files()
    assert not license_files
    assert len(recwarn) == 0
