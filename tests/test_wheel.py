from unittest.mock import Mock

from pdm.pep517 import wheel
from tests import FIXTURES


def test_override_tags_in_wheel_filename(monkeypatch):
    project = FIXTURES / "projects/demo-cextension"
    builder = wheel.WheelBuilder(
        project, config_settings={"--python-tag": "cp39", "--plat-name": "win_amd64"}
    )
    monkeypatch.setattr(wheel, "get_abi_tag", Mock(return_value="cp39"))
    assert builder.tag == "cp39-cp39-win_amd64"
