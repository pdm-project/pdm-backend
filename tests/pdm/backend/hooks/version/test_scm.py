import re
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union, cast

import pytest

from pdm.backend.hooks.version.scm import get_version_from_scm

# Copied from https://semver.org/
# fmt: off
_SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
      r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
# fmt: on


def increment_patch(version: str) -> str:
    m = _SEMVER_REGEX.match(version)
    assert m is not None, "Version provided doesn't match semver regex"

    result = [m["major"], ".", m["minor"], ".", str(int(m["patch"]) + 1)]
    if "prerelease" in m.groups():
        result.append("-")
        result.append(m["prerelease"])

    if "buildmetadata" in m.groups():
        result.append("+")
        result.append(m["buildmetadata"])

    return "".join(result)


class Scm(ABC):
    """Common interface for different source code management solutions"""

    __slots__ = (
        "_cmd",
        "_cwd",
    )

    def __init__(self, cmd: Path, cwd: Path) -> None:
        """Creates a new Scm

        Args:
            cmd: The base command to use for the scm
            cwd: The working directory to use when running these commands
        """
        self._cmd = cmd
        self._cwd = cwd

        self._init()

    def run(self, *args: Union[str, Path]):
        result = subprocess.run(
            [self._cmd, *args],
            capture_output=True,
            encoding="utf-8",
            check=True,
            cwd=self._cwd,
        )
        return result.stdout

    @abstractmethod
    def _init(self):
        """Initializes the SCM system in the provided directory"""
        ...

    @abstractmethod
    def commit(self, commit_message: str, files: List[Path]):
        """Creates a commit

        Args:
            commit_message: The message to store for the commit
            files: The files to include when creating the commit
        """
        ...

    @abstractmethod
    def tag(self, name: str):
        """Create a tag

        Args:
            name: The name for the provided tag
        """
        ...

    @property
    @abstractmethod
    def current_hash(self) -> str: ...


class GitScm(Scm):
    def __init__(self, cmd: Path, cwd: Path) -> None:
        super().__init__(cmd, cwd)
        self.run("config", "commit.gpgsign", "false")

    def _init(self):
        self.run("init")

    def commit(self, commit_message: str, files: List[Path]):
        self.run("add", *files)
        self.run("commit", "-m", commit_message)

    def tag(self, name: str):
        self.run("tag", "-am", "some tag", name)

    @property
    def current_hash(self) -> str:
        return "g" + self.run("rev-parse", "--short", "HEAD").strip()


class HgScm(Scm):
    def _init(self):
        self.run("init")

    def commit(self, commit_message: str, files: List[Path]):
        self.run("add", *files)
        self.run("commit", "-m", commit_message, *files)

    def tag(self, name: str):
        self.run("tag", name)

    @property
    def current_hash(self) -> str:
        return self.run("id", "-i").strip()


@pytest.fixture
def scm_dir() -> Iterable:
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def git(scm_dir: Path) -> GitScm:
    git = shutil.which("git")
    if git is None:
        pytest.skip("Cannot find git in path")

    scm = GitScm(Path(git), scm_dir)

    return scm


@pytest.fixture
def hg(scm_dir: Path) -> HgScm:
    hg = shutil.which("hg")
    if hg is None:
        pytest.skip("Cannot find hg in path")

    scm = HgScm(Path(hg), scm_dir)

    return scm


@pytest.fixture(params=["git", "hg"])
def scm(request: pytest.FixtureRequest, scm_dir: Path) -> Scm:
    scm = cast(Scm, request.getfixturevalue(request.param))

    file_path = scm_dir / "test.txt"
    with open(file_path, "w") as f:
        f.write("a\n")

    scm.commit("Add a", [file_path])

    return scm


def test__get_version_from_scm__returns_tag_if_method_unspecified(
    scm_dir: Path, scm: Scm
):
    expected_tag = "0.2.52"
    scm.tag(expected_tag)

    version = get_version_from_scm(scm_dir)

    assert version is not None
    assert version == expected_tag


def test__get_version_from_scm__adds_details_if_project_is_dirty(
    scm_dir: Path, scm: Scm
):
    expected_tag = "0.2.52"
    file_path = scm_dir / "some_file.txt"

    with open(file_path, "w") as f:
        f.write("having fun\n")
    scm.commit("some commit", [file_path])
    scm.tag(expected_tag)
    with open(file_path, "a") as f:
        f.write("having fun 2\n")

    version = get_version_from_scm(scm_dir)

    assert version is not None
    assert version == f"{expected_tag}+d{datetime.now(timezone.utc).strftime('%Y%m%d')}"


def test__get_version_from_scm__returns_version_if_tag_has_v(scm_dir: Path, scm: Scm):
    expected_tag = "0.2.52"
    scm.tag(f"v{expected_tag}")

    version = get_version_from_scm(scm_dir)

    assert version is not None
    assert version == expected_tag


def test__get_version_from_scm__returns_default_if_tag_cannot_be_parsed(
    scm_dir: Path, scm: Scm
):
    scm.tag("some-tag-without-numbers")

    version = get_version_from_scm(scm_dir)

    assert version is not None
    assert version == f"0.1.dev1+{scm.current_hash}"


def test__get_version_from_scm__tag_regex(scm_dir: Path, scm: Scm):
    expected_version = "7.2.9"
    tag_regex = "foo/bar-v(?P<version>.*)"
    scm.tag(f"foo/bar-v{expected_version}")

    version = get_version_from_scm(scm_dir, tag_regex=tag_regex)

    assert version is not None
    assert version == expected_version


@pytest.mark.parametrize("index", [0, 1])
def test__get_version_from_scm__selects_by_tag_filter_on_same_commit(
    scm_dir: Path, scm: Scm, index: int
):
    expected_versions = ["4.8.2", "2.4.9"]
    tag_regex = r"tag-\d/(?P<version>.*)"
    for i, version in enumerate(expected_versions):
        scm.tag(f"tag-{i}/v{version}")

    version = get_version_from_scm(
        scm_dir, tag_regex=tag_regex, tag_filter=f"tag-{index}/v*"
    )

    assert version is not None
    assert version == expected_versions[index]


@pytest.mark.parametrize("index", [0, 1])
def test__get_version_from_scm__selects_by_tag_filter_on_different_commits(
    scm_dir: Path, scm: Scm, index: int
):
    expected_versions = ["4.8.2", "2.4.9"]
    tag_regex = r"tag-\d/(?P<version>.*)"
    for i, version in enumerate(expected_versions):
        file_path = scm_dir / "test_{i}.txt"
        with open(file_path, "w") as f:
            f.write(f"Testing {i}\n")
        scm.commit(f"Add {i}", [file_path])
        scm.tag(f"tag-{i}/v{version}")

    file_path = scm_dir / "test_end.txt"
    with open(file_path, "w") as f:
        f.write("Testing end\n")
    scm.commit("Add end", [file_path])

    version = get_version_from_scm(
        scm_dir, tag_regex=tag_regex, tag_filter=f"tag-{index}/v*"
    )

    num_patches = len(expected_versions) - index
    next_version = increment_patch(expected_versions[index])
    assert version is not None
    assert version == f"{next_version}.dev{num_patches}+{scm.current_hash}"
