import sys

import pytest

from pdm.pep517 import wheel
from tests import FIXTURES


@pytest.mark.skipif(hasattr(sys, "pypy_version_info"), reason="invalid on PyPy3")
def test_override_tags_in_wheel_filename() -> None:
    project = FIXTURES / "projects/demo-cextension"
    builder = wheel.WheelBuilder(
        project,
        config_settings={"--py-limited-api": "cp36", "--plat-name": "win_amd64"},
    )
    assert builder.tag == "cp36-abi3-win_amd64"


def test_dist_info_name_with_no_version() -> None:
    project = FIXTURES / "projects/demo-no-version"
    builder = wheel.WheelBuilder(project)
    assert builder.dist_info_name == "demo-0.0.0.dist-info"
    assert builder.wheel_filename == "demo-0.0.0-py3-none-any.whl"
