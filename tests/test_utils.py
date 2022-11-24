from pdm.backend.utils import expand_vars


def test_expand_vars(monkeypatch):
    monkeypatch.setenv("FOO", "foo=a")
    monkeypatch.setenv("BAR", "bar")
    root = "/abc/def"

    line = "file:///${PROJECT_ROOT}/${FOO}:${BAR}:${BAZ}"
    assert expand_vars(line, root) == "file:///abc/def/foo%3Da:bar:${BAZ}"
