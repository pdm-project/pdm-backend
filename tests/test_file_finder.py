from pathlib import Path

from pdm.pep517 import utils
from pdm.pep517.base import Builder
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
