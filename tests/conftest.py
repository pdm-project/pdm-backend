import shutil
import subprocess
from pathlib import Path

import pytest

from tests import FIXTURES


@pytest.fixture
def fixture_project(tmp_path: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = FIXTURES / "projects" / name
    shutil.copytree(project, tmp_path / name)
    monkeypatch.chdir(tmp_path / name)
    return tmp_path / name


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
