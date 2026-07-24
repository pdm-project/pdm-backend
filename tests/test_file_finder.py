from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from pdm.backend.base import Builder, is_same_or_descendant_path
from pdm.backend.config import tomllib
from pdm.backend.exceptions import ValidationError
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


def test_sdist_rewrites_project_files_outside_project_root(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    project = repository / "packages" / "demo"
    project.mkdir(parents=True)
    readme = repository / "README.md"
    license_file = repository / "LICENSE"
    readme.write_text("# Demo\n")
    license_file.write_text("MIT\n")
    (project / "README.md").write_text("# Local demo\n")
    (project / "LICENSE").write_text("Local license\n")
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        """\
[build-system]
requires = ["pdm-backend"]
build-backend = "pdm.backend"

[project]
name = "demo"
version = "0.1.0"
readme = "../../README.md"
license = {file = "../../LICENSE"}

[tool.pdm.build]
source-includes = ["README.md", "LICENSE"]
"""
    )
    original_pyproject = pyproject.read_bytes()

    with SdistBuilder(project) as builder:
        artifact = builder.build(tmp_path / "dist")
        assert builder.config.metadata["readme"] == ".pdm-external/README.md"
        assert builder.config.metadata["license"]["file"] == ".pdm-external/LICENSE"

    assert pyproject.read_bytes() == original_pyproject
    assert readme.read_text() == "# Demo\n"
    assert license_file.read_text() == "MIT\n"
    with tarfile.open(artifact, "r:gz") as tar:

        def read_file(name: str) -> bytes:
            file = tar.extractfile(name)
            assert file is not None
            return file.read()

        names = tar.getnames()
        assert all(".." not in Path(name).parts for name in names)
        assert "demo-0.1.0/README.md" in names
        assert "demo-0.1.0/LICENSE" in names
        assert "demo-0.1.0/.pdm-external/README.md" in names
        assert "demo-0.1.0/.pdm-external/LICENSE" in names
        assert read_file("demo-0.1.0/README.md") == b"# Local demo\n"
        assert read_file("demo-0.1.0/LICENSE") == b"Local license\n"
        assert read_file("demo-0.1.0/.pdm-external/README.md") == b"# Demo\n"
        assert read_file("demo-0.1.0/.pdm-external/LICENSE") == b"MIT\n"
        data = tomllib.loads(read_file("demo-0.1.0/pyproject.toml").decode())

    assert data["project"]["readme"] == ".pdm-external/README.md"
    assert data["project"]["license"]["file"] == ".pdm-external/LICENSE"


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


def test_license_file_matching() -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-licenses")
    builder.config.metadata["license-files"] = ["LICENSE"]
    with builder:
        license_files = builder.find_license_files(builder.config.validate())
    assert license_files == ["LICENSE"]


def test_license_file_glob_matching() -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-licenses")
    with builder:
        license_files = sorted(builder.find_license_files(builder.config.validate()))
    assert license_files == [
        "LICENSE",
        "licenses/LICENSE.APACHE.md",
        "licenses/LICENSE.MIT.md",
    ]


def test_default_license_files() -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-licenses")
    del builder.config.metadata["license-files"]
    with builder:
        license_files = builder.find_license_files(builder.config.validate())
    assert license_files == ["LICENSE"]


def test_license_file_paths_no_matching() -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-licenses")
    builder.config.metadata["license-files"] = ["LICENSE.md"]
    with pytest.raises(ValidationError, match=".*must match at least one file"):
        builder.config.validate()


def test_license_file_explicit_empty() -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-licenses")
    builder.config.metadata["license-files"] = []
    with builder:
        license_files = list(builder.find_license_files(builder.config.validate()))
    assert not license_files


def test_collect_build_files_with_src_layout(tmp_path) -> None:
    builder = WheelBuilder(FIXTURES / "projects/demo-src-package")
    with builder:
        context = builder.build_context(tmp_path)
        builder.clean(context)
        builder.initialize(context)
        build_dir = context.ensure_build_dir()
        (build_dir / "my_package").mkdir()
        (build_dir / "my_package" / "hello.py").write_text("print('hello')\n")
        files = dict(builder.get_files(context))
        assert "my_package/hello.py" in files
