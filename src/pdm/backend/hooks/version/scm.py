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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from pdm.backend._vendor.packaging.version import Version

if TYPE_CHECKING:
    from _typeshed import StrPath

DEFAULT_TAG_REGEX = re.compile(
    r"^(?:[\w-]+-)?(?P<version>[vV]?\d+(?:\.\d+){0,2}[^\+]*)(?:\+.*)?$"
)


@dataclass(frozen=True)
class Config:
    tag_regex: re.Pattern
    tag_filter: str | None


def _subprocess_call(
    cmd: str | list[str],
    cwd: StrPath | None = None,
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


class SCMVersion(NamedTuple):
    version: Version
    distance: int | None
    dirty: bool
    node: str | None
    branch: str | None


def meta(
    config: Config,
    tag: str | Version,
    distance: int | None = None,
    dirty: bool = False,
    node: str | None = None,
    branch: str | None = None,
) -> SCMVersion:
    if isinstance(tag, str):
        tag = tag_to_version(config, tag)
    return SCMVersion(tag, distance, dirty, node, branch)


def _git_get_branch(root: StrPath) -> str | None:
    ret, out, _ = _subprocess_call("git rev-parse --abbrev-ref HEAD", root)
    if not ret:
        return out
    return None


def _git_is_dirty(root: StrPath) -> bool:
    _, out, _ = _subprocess_call("git status --porcelain --untracked-files=no", root)
    return bool(out)


def _git_get_node(root: StrPath) -> str | None:
    ret, out, _ = _subprocess_call("git rev-parse --verify --quiet HEAD", root)
    if not ret:
        return out[:7]
    return None


def _git_count_all_nodes(root: StrPath) -> int:
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


def _parse_version_tag(config: Config, tag: str) -> _ParseResult | None:
    tagstring = tag if not isinstance(tag, str) else str(tag)
    match = config.tag_regex.match(tagstring)

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


def tag_to_version(config: Config, tag: str) -> Version:
    """
    take a tag that might be prefixed with a keyword and return only the version part
    :param config: optional configuration object
    """
    tagdict = _parse_version_tag(config, tag)
    if not tagdict or not tagdict.version:
        warnings.warn(f"tag {tag!r} no version found")
        return Version("0.0.0")

    version = tagdict.version

    if tagdict.suffix:
        warnings.warn(f"tag {tag!r} will be stripped of its suffix {tagdict.suffix!r}")

    return Version(version)


def git_parse_version(root: StrPath, config: Config) -> SCMVersion | None:
    git = shutil.which("git")
    if not git:
        return None

    ret, repo, _ = _subprocess_call([git, "rev-parse", "--show-toplevel"], root)
    if ret or not repo:
        return None

    if os.path.isfile(os.path.join(repo, ".git/shallow")):
        warnings.warn(f"{repo!r} is shallow and may cause errors")
    describe_cmd = [
        git,
        "describe",
        "--dirty",
        "--tags",
        "--long",
        "--match",
        config.tag_filter or "*.*",
    ]
    ret, output, _ = _subprocess_call(describe_cmd, repo)
    branch = _git_get_branch(repo)

    if ret:
        rev_node = _git_get_node(repo)
        dirty = _git_is_dirty(repo)
        if rev_node is None:
            return meta(config, "0.0", 0, dirty)
        return meta(
            config, "0.0", _git_count_all_nodes(repo), dirty, f"g{rev_node}", branch
        )
    else:
        tag, number, node, dirty = _git_parse_describe(output)
        return meta(config, tag, number or None, dirty, node, branch)


def get_distance_revset(tag: str | None) -> str:
    return (
        "(branch(.)"  # look for revisions in this branch only
        " and {rev}::."  # after the last tag
        # ignore commits that only modify .hgtags and nothing else:
        " and (merge() or file('re:^(?!\\.hgtags).*$'))"
        " and not {rev})"  # ignore the tagged commit itself
    ).format(rev=f"tag({tag!r})" if tag is not None else "null")


def hg_get_graph_distance(root: StrPath, tag: str | None) -> int:
    cmd = ["hg", "log", "-q", "-r", get_distance_revset(tag)]
    _, out, _ = _subprocess_call(cmd, root)
    return len(out.strip().splitlines())


def _hg_tagdist_normalize_tagcommit(
    config: Config,
    tag: str,
    dist: int,
    node: str,
    branch: str,
    dirty: bool,
) -> SCMVersion:
    return meta(
        config, tag, distance=dist or None, node=node, dirty=dirty, branch=branch
    )


def guess_next_version(tag_version: Version) -> str:
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


def hg_parse_version(root: StrPath, config: Config) -> SCMVersion | None:
    hg = shutil.which("hg")
    if not hg:
        return None

    tag_filter = config.tag_filter or "\\."
    _, output, _ = _subprocess_call(
        [
            hg,
            "log",
            "-r",
            ".",
            "--template",
            f"{{latesttag(r're:{tag_filter}')}}-{{node|short}}-{{branch}}",
        ],
        root,
    )
    tag: str | None
    try:
        tag, node, branch = output.rsplit("-", 2)
    except ValueError:
        return None  # unpacking failed, unexpected hg repo
    # If no tag exists passes the tag filter.
    if tag == "null":
        tag = None

    _, id_output, _ = _subprocess_call(
        [hg, "id", "-i"],
        root,
    )
    dirty = id_output.endswith("+")
    try:
        dist = hg_get_graph_distance(root, tag)
        if tag is None:
            tag = "0.0"
        return _hg_tagdist_normalize_tagcommit(
            config, tag, dist, node, branch, dirty=dirty
        )
    except ValueError:
        return None  # unpacking failed, old hg


def default_version_formatter(version: SCMVersion) -> str:
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
    local_version = fmt.format(node=version.node, time=datetime.now(tz=timezone.utc))
    return main_version + local_version


def get_version_from_scm(
    root: str | Path, *, tag_regex: str | None = None, tag_filter: str | None = None
) -> SCMVersion | None:
    config = Config(
        tag_regex=re.compile(tag_regex) if tag_regex else DEFAULT_TAG_REGEX,
        tag_filter=tag_filter,
    )
    for func in (git_parse_version, hg_parse_version):
        version = func(root, config)
        if version:
            return version
    return None
