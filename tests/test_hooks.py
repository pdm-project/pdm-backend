import shutil
from unittest.mock import Mock

import pytest

from pdm.backend.wheel import WheelBuilder
from tests import FIXTURES
from tests.fixtures.hooks import hook_class, hook_module


def make_entry_point(hook):
    ep = Mock()
    ep.load.return_value = hook
    return ep


@pytest.fixture()
def project_with_hooks(monkeypatch, tmp_path):
    hooks = [
        make_entry_point(hook_module),
        make_entry_point(hook_class.hook3),
        make_entry_point(hook_class.BuildHook),
    ]
    monkeypatch.setattr("pdm.backend.base.entry_points", Mock(return_value=hooks))
    project = FIXTURES / "projects/demo-purelib-with-build"
    shutil.copytree(project, tmp_path / project.name)
    shutil.copy2(
        FIXTURES / "hooks/local_hook.py", tmp_path / project.name / "my_build.py"
    )
    return tmp_path / project.name


def test_load_hooks(project_with_hooks, caplog: pytest.LogCaptureFixture):
    builder = WheelBuilder(project_with_hooks)
    hooks = builder._hooks
    assert len(hooks) == 6
    assert hooks[:4] == WheelBuilder.hooks + [hook_module, hook_class.hook3]
    assert isinstance(hooks[4], hook_class.BuildHook)

    caplog.set_level("INFO", logger="hooks")
    with builder:
        builder.build(str(project_with_hooks / "dist"))

    messages = [record.message for record in caplog.records if record.name == "hooks"]
    for num in range(1, 5):
        assert f"Hook{num} build clean called" in messages
        assert f"Hook{num} build initialize called" in messages
        assert f"Hook{num} build update files called" in messages
        assert f"Hook{num} build finalize called" in messages
