"""
module to get version from tag of SCM repository.
Adapted from setuptools-scm. Currently only support git and hg.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, NamedTuple

from pdm.backend._vendor.packaging.version import LegacyVersion, Version
from pdm.backend._vendor.packaging.version import parse as parse_version

DEFAULT_TAG_REGEX = re.compile(
    r"^(?:[\w-]+-)?(?P<version>[vV]?\d+(?:\.\d+){0,2}[^\+]*)(?:\+.*)?$"
)


def _subprocess_call(
    cmd: str | list[str],
    cwd: os.PathLike | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    # adapted from pre-commit
    # Too many bugs dealing with environment variables and GIT:
    # https://github.com/pre-commit/pre-commit/issues/300
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("GIT_")
        or k in ("GIT_EXEC_PATH", "GIT_SSH", "GIT_SSH_COMMAND")
    }
    env.update({"LC_ALL": "C", "LANG": "", "HGPLAIN": "1"})
    if extra_env:
        env.update(extra_env)
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate()
    return (
        proc.returncode,
        out.decode("utf-8", "surrogateescape").strip(),
        err.decode("utf-8", "surrogateescape").strip(),
    )


class VersionInfo(NamedTuple):
    version: Version | LegacyVersion
    distance: int | None
    dirty: bool
    node: str | None
    branch: str | None


def meta(
    tag: str | Version | LegacyVersion,
    distance: int | None = None,
    dirty: bool = False,
    node: str | None = None,
    branch: str | None = None,
) -> VersionInfo:
    if isinstance(tag, str):
        tag = tag_to_version(tag)
    return VersionInfo(tag, distance, dirty, node, branch)


def _git_get_branch(root: os.PathLike[Any]) -> str | None:
    ret, out, _ = _subprocess_call("git rev-parse --abbrev-ref HEAD", root)
    if not ret:
        return out
    return None


def _git_is_dirty(root: os.PathLike[Any]) -> bool:
    _, out, _ = _subprocess_call("git status --porcelain --untracked-files=no", root)
    return bool(out)


def _git_get_node(root: os.PathLike[Any]) -> str | None:
    ret, out, _ = _subprocess_call("git rev-parse --verify --quiet HEAD", root)
    if not ret:
        return out[:7]
    return None


def _git_count_all_nodes(root: os.PathLike[Any]) -> int:
    _, out, _ = _subprocess_call("git rev-list HEAD", root)
    return out.count("\n") + 1


def _git_parse_describe(describe_output: str) -> tuple[str, int, str, bool]:
    # 'describe_output' looks e.g. like 'v1.5.0-0-g4060507' or
    # 'v1.15.1rc1-37-g9bd1298-dirty'.

    if describe_output.endswith("-dirty"):
        dirty = True
        describe_output = describe_output[:-6]
    else:
        dirty = False

    tag, number, node = describe_output.rsplit("-", 2)
    return tag, int(number), node, dirty


class _ParseResult(NamedTuple):
    version: str
    prefix: str
    suffix: str


def _parse_version_tag(tag: str) -> _ParseResult | None:
    tagstring = tag if not isinstance(tag, str) else str(tag)
    match = DEFAULT_TAG_REGEX.match(tagstring)

    result = None
    if match:
        if len(match.groups()) == 1:
            key: int | str = 1
        else:
            key = "version"

        result = _ParseResult(
            match.group(key),
            match.group(0)[: match.start(key)],
            match.group(0)[match.end(key) :],
        )

    return result


def tag_to_version(tag: str) -> Version | LegacyVersion:
    """
    take a tag that might be prefixed with a keyword and return only the version part
    :param config: optional configuration object
    """
    tagdict = _parse_version_tag(tag)
    if not tagdict or not tagdict.version:
        warnings.warn(f"tag {tag!r} no version found")
        return Version("0.0.0")

    version = tagdict.version

    if tagdict.suffix:
        warnings.warn(f"tag {tag!r} will be stripped of its suffix '{tagdict.suffix}'")

    return parse_version(version)


def tags_to_versions(tags: Iterable[str]) -> list[Version | LegacyVersion]:
    """
    take tags that might be prefixed with a keyword and return only the version part
    :param tags: an iterable of tags
    :param config: optional configuration object
    """
    return [tag_to_version(tag) for tag in tags if tag]


def git_parse_version(root: os.PathLike[Any]) -> VersionInfo | None:
    GIT = shutil.which("git")
    if not GIT:
        return None

    ret, repo, _ = _subprocess_call([GIT, "rev-parse", "--show-toplevel"], root)
    if ret or not os.path.samefile(root, repo):
        return None

    if os.path.isfile(os.path.join(root, ".git/shallow")):
        warnings.warn(f'"{root}" is shallow and may cause errors')
    describe_cmd = [GIT, "describe", "--dirty", "--tags", "--long", "--match", "*.*"]
    ret, output, err = _subprocess_call(describe_cmd, root)
    branch = _git_get_branch(root)

    if ret:
        rev_node = _git_get_node(root)
        dirty = _git_is_dirty(root)
        if rev_node is None:
            return meta("0.0", 0, dirty)
        return meta("0.0", _git_count_all_nodes(root), dirty, f"g{rev_node}", branch)
    else:
        tag, number, node, dirty = _git_parse_describe(output)
        return meta(tag, number or None, dirty, node, branch)


def get_latest_normalizable_tag(root: os.PathLike[Any]) -> str:
    # Gets all tags containing a '.' from oldest to newest
    cmd = [
        "hg",
        "log",
        "-r",
        "ancestors(.) and tag('re:\\.')",
        "--template",
        "{tags}\n",
    ]
    _, output, _ = _subprocess_call(cmd, root)
    outlines = output.split()
    if not outlines:
        return "null"
    tag = outlines[-1].split()[-1]
    return tag


def hg_get_graph_distance(root: os.PathLike[Any], rev1: str, rev2: str = ".") -> int:
    cmd = ["hg", "log", "-q", "-r", f"{rev1}::{rev2}"]
    _, out, _ = _subprocess_call(cmd, root)
    return len(out.strip().splitlines()) - 1


def _hg_tagdist_normalize_tagcommit(
    root: os.PathLike[Any], tag: str, dist: int, node: str, branch: str
) -> VersionInfo:
    dirty = node.endswith("+")
    node = "h" + node.strip("+")

    # Detect changes since the specified tag
    revset = (
        "(branch(.)"  # look for revisions in this branch only
        " and tag({tag!r})::."  # after the last tag
        # ignore commits that only modify .hgtags and nothing else:
        " and (merge() or file('re:^(?!\\.hgtags).*$'))"
        " and not tag({tag!r}))"  # ignore the tagged commit itself
    ).format(tag=tag)
    if tag != "0.0":
        _, commits, _ = _subprocess_call(
            ["hg", "log", "-r", revset, "--template", "{node|short}"],
            root,
        )
    else:
        commits = "True"

    if commits or dirty:
        return meta(tag, distance=dist, node=node, dirty=dirty, branch=branch)
    else:
        return meta(tag)


def guess_next_version(tag_version: Version | LegacyVersion) -> str:
    version = _strip_local(str(tag_version))
    return _bump_dev(version) or _bump_regex(version)


def _strip_local(version_string: str) -> str:
    public, _, _ = version_string.partition("+")
    return public


def _bump_dev(version: str) -> str:
    if ".dev" not in version:
        return ""

    prefix, tail = version.rsplit(".dev", 1)
    assert tail == "0", "own dev numbers are unsupported"
    return prefix


def _bump_regex(version: str) -> str:
    match = re.match(r"(.*?)(\d+)$", version)
    assert match is not None
    prefix, tail = match.groups()
    return "%s%d" % (prefix, int(tail) + 1)


def hg_parse_version(root: os.PathLike[Any]) -> VersionInfo | None:
    if not shutil.which("hg"):
        return None
    _, output, _ = _subprocess_call("hg id -i -b -t", root)
    identity_data = output.split()
    if not identity_data:
        return None
    node = identity_data.pop(0)
    branch = identity_data.pop(0)
    if "tip" in identity_data:
        # tip is not a real tag
        identity_data.remove("tip")
    tags = tags_to_versions(identity_data)
    dirty = node[-1] == "+"
    if tags:
        return meta(tags[0], dirty=dirty, branch=branch)

    if node.strip("+") == "0" * 12:
        return meta("0.0", dirty=dirty, branch=branch)

    try:
        tag = get_latest_normalizable_tag(root)
        dist = hg_get_graph_distance(root, tag)
        if tag == "null":
            tag = "0.0"
            dist = int(dist) + 1
        return _hg_tagdist_normalize_tagcommit(root, tag, dist, node, branch)
    except ValueError:
        return None  # unpacking failed, old hg


def format_version(version: VersionInfo) -> str:
    if version.distance is None:
        main_version = str(version.version)
    else:
        guessed = guess_next_version(version.version)
        main_version = f"{guessed}.dev{version.distance}"

    if version.distance is None or version.node is None:
        clean_format = ""
        dirty_format = "+d{time:%Y%m%d}"
    else:
        clean_format = "+{node}"
        dirty_format = "+{node}.d{time:%Y%m%d}"
    fmt = dirty_format if version.dirty else clean_format
    local_version = fmt.format(node=version.node, time=datetime.utcnow())
    return main_version + local_version


def get_version_from_scm(root: str | Path) -> str:
    for func in (git_parse_version, hg_parse_version):
        version = func(root)  # type: ignore
        if version:
            break
    else:
        version = meta("0.0.0")
    assert version is not None
    return format_version(version)
