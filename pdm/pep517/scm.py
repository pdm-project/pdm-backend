"""
module to get version from tag of SCM repository.
Adapted from setuptools-scm. Currently only support git and hg.
"""
import os
import re
import shlex
import shutil
import subprocess
import warnings
from collections import namedtuple
from datetime import datetime
from typing import Optional, Tuple

from pdm.pep517._vendor.packaging.version import parse as parse_version

DEFAULT_TAG_REGEX = re.compile(
    r"^(?:[\w-]+-)?(?P<version>[vV]?\d+(?:\.\d+){0,2}[^\+]*)(?:\+.*)?$"
)


def _subprocess_call(cmd, cwd=None, extra_env=None) -> Tuple[int, str, str]:
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


VersionInfo = namedtuple("VersionInfo", "version,distance,node,dirty,branch")


def meta(
    tag,
    distance=None,
    dirty=False,
    node=None,
    branch=None,
):
    if isinstance(tag, str):
        tag = tag_to_version(tag)
    return VersionInfo(tag, distance, dirty, node, branch)


def _git_get_branch(root: os.PathLike) -> Optional[str]:
    ret, out, _ = _subprocess_call("git rev-parse --abbrev-ref HEAD", root)
    if not ret:
        return out


def _git_is_dirty(root: os.PathLike) -> bool:
    _, out, _ = _subprocess_call("git status --porcelain --untracked-files=no", root)
    return bool(out)


def _git_get_node(root: os.PathLike) -> Optional[str]:
    ret, out, _ = _subprocess_call("git rev-parse --verify --quiet HEAD", root)
    if not ret:
        return out[:7]


def _git_count_all_nodes(root: os.PathLike) -> int:
    _, out, _ = _subprocess_call("git rev-list HEAD", root)
    return out.count("\n") + 1


def _git_parse_describe(describe_output):
    # 'describe_output' looks e.g. like 'v1.5.0-0-g4060507' or
    # 'v1.15.1rc1-37-g9bd1298-dirty'.

    if describe_output.endswith("-dirty"):
        dirty = True
        describe_output = describe_output[:-6]
    else:
        dirty = False

    tag, number, node = describe_output.rsplit("-", 2)
    number = int(number)
    return tag, number, node, dirty


def _parse_version_tag(tag):
    tagstring = tag if not isinstance(tag, str) else str(tag)
    match = DEFAULT_TAG_REGEX.match(tagstring)

    result = None
    if match:
        if len(match.groups()) == 1:
            key = 1
        else:
            key = "version"

        result = {
            "version": match.group(key),
            "prefix": match.group(0)[: match.start(key)],
            "suffix": match.group(0)[match.end(key) :],
        }

    return result


def tag_to_version(tag):
    """
    take a tag that might be prefixed with a keyword and return only the version part
    :param config: optional configuration object
    """
    tagdict = _parse_version_tag(tag)
    if not isinstance(tagdict, dict) or not tagdict.get("version", None):
        warnings.warn("tag {!r} no version found".format(tag))
        return None

    version = tagdict["version"]

    if tagdict.get("suffix", ""):
        warnings.warn(
            "tag {!r} will be stripped of its suffix '{}'".format(
                tag, tagdict["suffix"]
            )
        )

    version = parse_version(version)

    return version


def tags_to_versions(tags):
    """
    take tags that might be prefixed with a keyword and return only the version part
    :param tags: an iterable of tags
    :param config: optional configuration object
    """
    return [tag_to_version(tag) for tag in tags if tag]


def git_parse_version(root: os.PathLike) -> Optional[VersionInfo]:
    GIT = shutil.which("git")
    if not GIT:
        return

    ret, repo, _ = _subprocess_call([GIT, "rev-parse", "--show-toplevel"], root)
    if ret or not os.path.samefile(root, repo):
        return

    if os.path.isfile(os.path.join(root, ".git/shallow")):
        warnings.warn('"{}" is shallow and may cause errors'.format(root))
    describe_cmd = [GIT, "describe", "--dirty", "--tags", "--long", "--match", "*.*"]
    ret, output, err = _subprocess_call(describe_cmd, root)
    branch = _git_get_branch(root)

    if ret:
        rev_node = _git_get_node(root)
        dirty = _git_is_dirty(root)
        if rev_node is None:
            return meta("0.0", 0, dirty)
        return meta("0.0", _git_count_all_nodes(root), f"g{rev_node}", dirty, branch)
    else:
        tag, number, node, dirty = _git_parse_describe(output)
        return meta(tag, number or None, node, dirty, branch)


def get_latest_normalizable_tag(root):
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


def hg_get_graph_distance(root, rev1, rev2="."):
    cmd = ["hg", "log", "-q", "-r", "{}::{}".format(rev1, rev2)]
    _, out, _ = _subprocess_call(cmd, root)
    return len(out.strip().splitlines()) - 1


def _hg_tagdist_normalize_tagcommit(root, tag, dist, node, branch):
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
        commits = True

    if commits or dirty:
        return meta(tag, distance=dist, node=node, dirty=dirty, branch=branch)
    else:
        return meta(tag)


def guess_next_version(tag_version):
    version = _strip_local(str(tag_version))
    return _bump_dev(version) or _bump_regex(version)


def _strip_local(version_string):
    public, _, _ = version_string.partition("+")
    return public


def _bump_dev(version):
    if ".dev" not in version:
        return

    prefix, tail = version.rsplit(".dev", 1)
    assert tail == "0", "own dev numbers are unsupported"
    return prefix


def _bump_regex(version):
    prefix, tail = re.match(r"(.*?)(\d+)$", version).groups()
    return "%s%d" % (prefix, int(tail) + 1)


def hg_parse_version(root: os.PathLike) -> Optional[VersionInfo]:
    if not shutil.which("hg"):
        return
    _, identity_data, _ = _subprocess_call("hg id -i -b -t", root)
    identity_data = identity_data.split()
    if not identity_data:
        return
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
        pass  # unpacking failed, old hg


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


def get_version_from_scm(root: os.PathLike) -> str:
    for func in (git_parse_version, hg_parse_version):
        version = func(root)
        if version:
            break
    else:
        version = meta("0.0.0")
    return format_version(version)
