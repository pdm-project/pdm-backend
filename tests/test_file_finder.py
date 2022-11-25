from __future__ import annotations

from pathlib import Path

import pytest

from pdm.backend.base import Builder, is_same_or_descendant_path
from pdm.backend.sdist import SdistBuilder
from pdm.backend.wheel import WheelBuilder
from tests import FIXTURES


@pytest.mark.parametrize("builder_cls", (WheelBuilder, SdistBuilder))
def test_auto_include_tests_for_sdist(
    builder_cls: type[Builder], tmp_path: Path
) -> None:
    with builder_cls(FIXTURES / "projects/demo-package-with-tests") as builder:
        context = builder.build_context(tmp_path)
        builder.clean(context)
        builder.initialize(context)
        files = dict(builder.get_files(context))

    sdist_only_files = ("tests/__init__.py", "pyproject.toml")
    include_files = ("my_package/__init__.py",)
    for file in include_files:
        assert file in files

    for file in sdist_only_files:
        if isinstance(builder, SdistBuilder):
            assert file in files
        else:
            assert file not in files


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


@pytest.mark.parametrize("builder_cls", (WheelBuilder, SdistBuilder))
def test_recursive_glob_patterns_in_includes(
    builder_cls: type[Builder], tmp_path: Path
) -> None:
    with builder_cls(FIXTURES / "projects/demo-package-with-deep-path") as builder:
        context = builder.build_context(tmp_path)
        builder.clean(context)
        builder.initialize(context)
        files = dict(builder.get_files(context))

    data_files = (
        "my_package/data/data_a.json",
        "my_package/data/data_inner/data_b.json",
    )

    assert "my_package/__init__.py" in files

    for file in data_files:
        if isinstance(builder, WheelBuilder):
            assert file not in files
        else:
            assert file in files


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
    includes, excludes, data_a_exist: bool, data_b_exist: bool, tmp_path: Path
) -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-package-with-deep-path")
    data_a = "my_package/data/data_a.json"
    data_b = "my_package/data/data_inner/data_b.json"

    with builder:
        context = builder.build_context(tmp_path)
        builder.clean(context)
        builder.initialize(context)
        builder.config.build_config["includes"] = includes
        builder.config.build_config["excludes"] = excludes
        builder.config.build_config["source-includes"] = []
        include_files = dict(builder.get_files(context))
        assert (data_a in include_files) == data_a_exist
        assert (data_b in include_files) == data_b_exist


def test_license_file_globs_no_matching(tmp_path: Path) -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-no-license")
    with builder:
        with pytest.warns(UserWarning) as warns:
            license_files = builder.find_license_files()

    assert not license_files
    assert len(warns) == 1
    assert str(warns.pop(UserWarning).message).startswith(
        "No license files are matched with glob patterns"
    )


def test_license_file_paths_no_matching(tmp_path: Path) -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-no-license")
    builder.config.metadata["license-files"] = {"paths": ["LICENSE"]}
    with builder:
        with pytest.raises(ValueError, match="License files not found"):
            builder.find_license_files()


@pytest.mark.parametrize("key", ["paths", "globs"])
def test_license_file_explicit_empty(recwarn, key, tmp_path) -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-no-license")
    builder.config.metadata["license-files"] = {key: []}
    with builder:
        license_files = builder.find_license_files()
    assert not license_files
    assert len(recwarn) == 0


def test_reuse_spec_licenses_dir(tmp_path) -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-reuse-spec")
    with builder:
        license_files = builder.find_license_files()
    assert license_files == ["LICENSES/MPL-2.0.txt"]
