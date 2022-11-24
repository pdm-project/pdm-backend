import shutil
import subprocess

import pytest

from pdm.backend import utils
from tests import FIXTURES


@pytest.fixture()
def project_with_scm(tmp_path):
    project = FIXTURES / "projects/demo-using-scm"
    shutil.copytree(project, tmp_path / project.name)
    with utils.cd(tmp_path / project.name):
        subprocess.check_call(["git", "init"])
        subprocess.check_call(["git", "config", "user.email", "you@any.com"])
        subprocess.check_call(["git", "config", "user.name", "Name"])
        subprocess.check_call(["git", "add", "."])
        subprocess.check_call(["git", "commit", "-m", "initial commit"])
        subprocess.check_call(["git", "tag", "-a", "0.1.0", "-m", "version 0.1.0"])
        yield tmp_path / project.name
