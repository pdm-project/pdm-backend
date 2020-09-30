import os
from pdm.pep517.requirements import Requirement

import pytest

from tests import FIXTURES

FILE_PREFIX = "file:///" if os.name == "nt" else "file://"

REQUIREMENTS = [
    ("requests", ("requests", "*")),
    ("requests<2.21.0,>=2.20.0", ("requests", "<2.21.0,>=2.20.0")),
    (
        'requests==2.19.0; os_name == "nt"',
        ("requests", {"version": "==2.19.0", "marker": 'os_name == "nt"'}),
    ),
    (
        "requests[security,tests]==2.8.*,>=2.8.1; python_version < '2.7'",
        (
            "requests",
            {
                "version": "==2.8.*,>=2.8.1",
                "marker": "python_version < '2.7'",
                "extras": ["security", "tests"],
            },
        ),
    ),
    (
        "pip @ https://github.com/pypa/pip/archive/1.3.1.zip",
        ("pip", {"url": "https://github.com/pypa/pip/archive/1.3.1.zip"}),
    ),
    (
        "MyProject @ git+http://git.example.com/MyProject.git"
        "@da9234ee9982d4bbb3c72346a6de940a148ea686",
        (
            "MyProject",
            {
                "git": "http://git.example.com/MyProject.git",
                "ref": "da9234ee9982d4bbb3c72346a6de940a148ea686",
            },
        ),
    ),
    (
        f"demo @ {FILE_PREFIX}"
        + (FIXTURES / "artifacts/demo-0.0.1-py2.py3-none-any.whl").as_posix(),
        (
            "demo",
            {
                "url": FILE_PREFIX
                + (FIXTURES / "artifacts/demo-0.0.1-py2.py3-none-any.whl").as_posix()
            },
        ),
    ),
    (
        f"demo[security] @ {FILE_PREFIX}" + (FIXTURES / "projects/demo").as_posix(),
        (
            "demo",
            {"path": (FIXTURES / "projects/demo").as_posix(), "extras": ["security"]},
        ),
    ),
    (
        "requests; python_version == '3.7.*'",
        ("requests", {"version": "*", "marker": "python_version == '3.7.*'"}),
    ),
    (
        "pip @ git+ssh://git@github.com/pypa/pip.git@1.3.1"
        "#7921be1537eac1e97bc40179a57f0349c2aee67d",
        (
            "pip",
            {
                "git": "ssh://git@github.com/pypa/pip.git",
                "ref": "7921be1537eac1e97bc40179a57f0349c2aee67d",
                "tag": "1.3.1",
            },
        ),
    ),
    (
        "pip @ git+ssh://git@github.com/pypa/pip.git@master"
        "#7921be1537eac1e97bc40179a57f0349c2aee67d",
        (
            "pip",
            {
                "git": "ssh://git@github.com/pypa/pip.git",
                "ref": "7921be1537eac1e97bc40179a57f0349c2aee67d",
                "branch": "master",
            },
        ),
    ),
]


@pytest.mark.parametrize("expected, params", REQUIREMENTS)
def test_convert_req_dict_to_req_line(expected, params):
    r = Requirement.from_req_dict(*params)
    assert r.as_line() == expected
