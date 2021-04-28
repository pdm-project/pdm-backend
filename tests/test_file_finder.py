from pathlib import Path

import pytest

from pdm.pep517 import utils
from pdm.pep517.base import Builder, is_same_or_descendant_path
from tests import FIXTURES


def test_auto_include_tests_for_sdist():
    builder = Builder(FIXTURES / "projects/demo-package-with-tests")
    with utils.cd(builder.location):
        sdist_files = builder.find_files_to_add(True)
        wheel_files = builder.find_files_to_add(False)

    sdist_only_files = ("tests/__init__.py", "LICENSE", "pyproject.toml")
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
def test_is_same_or_descendant_path(target, path, expect):
    assert is_same_or_descendant_path(target, path) == expect


def test_recursive_glob_patterns_in_includes():
    builder = Builder(FIXTURES / "projects/demo-package-with-deep-path")
    with utils.cd(builder.location):
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
