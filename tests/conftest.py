import shutil
import subprocess
from pathlib import Path
from typing import Generator

import pytest

from pdm.backend import utils
from tests import FIXTURES


@pytest.fixture
def fixture_project(tmp_path: Path, name: str) -> Generator[Path, None, None]:
    project = FIXTURES / "projects" / name
    shutil.copytree(project, tmp_path / name)
    with utils.cd(tmp_path / name):
        yield tmp_path / name


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    return tmp_path / "dist"


@pytest.fixture
def scm(fixture_project: Path) -> None:
    subprocess.check_call(["git", "init"])
    subprocess.check_call(["git", "config", "user.email", "you@any.com"])
    subprocess.check_call(["git", "config", "user.name", "Name"])
    subprocess.check_call(["git", "add", "."])
    subprocess.check_call(["git", "commit", "-m", "initial commit"])
    subprocess.check_call(["git", "tag", "-a", "0.1.0", "-m", "version 0.1.0"])
