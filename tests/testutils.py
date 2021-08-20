import contextlib
import tarfile
import zipfile

from pdm.pep517 import utils
from tests import FIXTURES


def get_tarball_names(path):
    with tarfile.open(path, "r:gz") as tar:
        return tar.getnames()


def get_wheel_names(path):
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


@contextlib.contextmanager
def build_fixture_project(project_name):
    project = FIXTURES / "projects" / project_name
    with utils.cd(project):
        yield project
