import sys
from pathlib import Path

import pytest

from pdm.backend import wheel
from tests import FIXTURES


@pytest.mark.skipif(hasattr(sys, "pypy_version_info"), reason="invalid on PyPy3")
def test_override_tags_in_wheel_filename() -> None:
    project = FIXTURES / "projects/demo-cextension"
    with wheel.WheelBuilder(
        project,
        config_settings={"--py-limited-api": "cp36", "--plat-name": "win_amd64"},
    ) as builder:
        assert builder.tag == "cp36-abi3-win_amd64"


def test_dist_info_name_with_no_version(tmp_path: Path) -> None:
    project = FIXTURES / "projects/demo-no-version"
    with wheel.WheelBuilder(project) as builder:
        builder.initialize(builder.build_context(tmp_path))
        assert builder.dist_info_name == "demo-0.0.0.dist-info"
        assert builder.tag == "py3-none-any"
