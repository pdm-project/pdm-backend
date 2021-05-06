from pdm.pep517 import wheel
from tests import FIXTURES


def test_override_tags_in_wheel_filename(monkeypatch):
    project = FIXTURES / "projects/demo-cextension"
    builder = wheel.WheelBuilder(
        project,
        config_settings={"--py-limited-api": "cp36", "--plat-name": "win_amd64"},
    )
    assert builder.tag == "cp36-abi3-win_amd64"
