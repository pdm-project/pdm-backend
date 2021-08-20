import os
import zipfile

from pdm.pep517.setuptools import build_editable
from tests.testutils import build_fixture_project


def test_build_editable_for_setuptools_backend(tmp_path):
    with build_fixture_project("demo-package-setuptools") as project:
        wheel = build_editable(tmp_path.as_posix())
        with zipfile.ZipFile(tmp_path / wheel) as zf:
            assert "demo.pth" in zf.namelist()
            content = zf.read("demo.pth")
            assert os.path.normcase(content.strip().decode()) == os.path.normcase(
                project
            )
