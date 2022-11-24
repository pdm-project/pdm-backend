import contextlib
import tarfile
import zipfile
from pathlib import Path
from typing import Iterator, List

from pdm.backend import utils
from tests import FIXTURES


def get_tarball_names(path: Path) -> List[str]:
    with tarfile.open(path, "r:gz") as tar:
        return tar.getnames()


def get_wheel_names(path: Path) -> List[str]:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


@contextlib.contextmanager
def build_fixture_project(project_name: str) -> Iterator[Path]:
    project = FIXTURES / "projects" / project_name
    with utils.cd(project):
        yield project
