import pytest

from pdm.pep517.validator import validate_pep621

VALID_DATA = [
    {
        "name": "foo",
        "version": "0.2.1",
        "readme": "README.md",
        "authors": [{"email": "hi@pradyunsg.me"}],
        "scripts": {"spam": "spam:main_cli"},
        "entry-points": {"rst": {"tomatoes": "spam:main_tomatoes"}},
        "dependencies": ["flask", "flask-login"],
        "optional-dependencies": {"mysql": ["mysqlclient"]},
    },
    {
        "name": "foo",
        "version": "0.1.0",
        "readme": {"file": "REAME.md", "content-type": "text/markdown"},
        "license": {"text": "MIT license"},
    },
    {
        "name": "foo",
        "version": "0.1.0",
        "readme": {"text": "Awesome project", "content-type": "text/plain"},
        "license": {"file": "LICENSE"},
    },
    {
        "name": "foo",
        "license-expression": "MIT",
        "license-files": {"paths": ["LICENSE"]},
    },
    {
        "name": "foo",
        "license-expression": "MIT",
        "license-files": {"globs": ["LICENSE*"]},
    },
]


INVALID_DATA = [
    {"version": "0.2.1"},  # missing required field
    {"name": "foo", "version": "0.2.1", "foo": "bar"},  # unknown field
    {"name": "foo", "dependencies": {"requests": "*"}},  # wrong type
    {
        "name": "foo",
        "readme": {
            "text": "Awesome project",
            "file": "README.md",
            "content-type": "text/markdown",
        },
    },  # mutually exclusive fields
    {"name": "foo", "version": {"from": "foo.py"}},
    {
        "name": "foo",
        "license-expression": "MIT",
        "license-files": {"paths": ["LICENSE"], "globs": ["LICENSE*"]},
    },
]


@pytest.mark.parametrize("data", VALID_DATA)
def test_validate_success(data):
    assert validate_pep621(data)


@pytest.mark.parametrize("data", INVALID_DATA)
def test_validate_error(data):
    assert not validate_pep621(data)
