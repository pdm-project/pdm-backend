import os

import pytest

from pdm.backend.utils import expand_vars

is_nt = os.name == "nt"


@pytest.mark.skipif(is_nt, reason="Posix path")
def test_expand_vars_posix(monkeypatch):
    monkeypatch.setenv("FOO", "foo=a")
    monkeypatch.setenv("BAR", "bar")
    root = "/abc/def"

    line = "file:///${PROJECT_ROOT}/${FOO}:${BAR}:${BAZ}"
    assert expand_vars(line, root) == "file:///abc/def/foo%3Da:bar:${BAZ}"


@pytest.mark.skipif(not is_nt, reason="Windows path")
def test_expand_vars_win(monkeypatch):
    monkeypatch.setenv("FOO", "foo=a")
    monkeypatch.setenv("BAR", "bar")
    root = "C:/abc/def"

    line = "file:///${PROJECT_ROOT}/${FOO}:${BAR}:${BAZ}"
    assert expand_vars(line, root) == "file:///C:/abc/def/foo%3Da:bar:${BAZ}"
