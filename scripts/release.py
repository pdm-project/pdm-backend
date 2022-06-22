import argparse
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple

import parver

PROJECT_DIR = Path(__file__).parent.parent
VERSION_RE = re.compile(r"^__version__ *= *([\"'])(.+?)\1 *$", flags=re.M)


class PythonVersionParser(HTMLParser):
    def __init__(self, *, convert_charrefs: bool = True) -> None:
        super().__init__(convert_charrefs=convert_charrefs)
        self._parsing_release_number_span = False
        self._parsing_release_number_a = False
        self.parsed_python_versions: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if tag == "span" and any(
            "release-number" in value for key, value in attrs if key == "class"
        ):
            self._parsing_release_number_span = True
            return

        if self._parsing_release_number_span and tag == "a":
            self._parsing_release_number_a = True

    def handle_endtag(self, tag: str) -> None:
        if self._parsing_release_number_span and tag == "span":
            self._parsing_release_number_span = False

        if self._parsing_release_number_a and tag == "a":
            self._parsing_release_number_a = False

    def handle_data(self, data: str) -> None:
        if self._parsing_release_number_a:
            self.parsed_python_versions.append(data[7:])


def _get_current_version():
    from pdm.pep517.base import Builder

    builder = Builder(PROJECT_DIR)
    return builder.meta.version


def _replace_version(new_version: str):
    target = PROJECT_DIR / "pdm/pep517/__init__.py"
    content = target.read_text("utf-8")
    target.write_text(VERSION_RE.sub(f'__version__ = "{new_version}"', content))


def _bump_version(pre=None, major=False, minor=False, patch=True):
    if not any([major, minor, patch]) and not pre:
        patch = True
    if len([v for v in [major, minor, patch] if v]) > 1:
        print(
            "Only one option should be provided among " "(--major, --minor, --patch)",
            file=sys.stderr,
        )
        sys.exit(1)
    version = parver.Version.parse(_get_current_version())
    if any([major, minor, patch]):
        version_idx = [major, minor, patch].index(True)
        version = version.replace(pre=None, post=None).bump_release(index=version_idx)
    if pre:
        if pre != version.pre_tag:
            version = version.replace(pre=None)
        version = version.bump_pre(pre)
    version = version.replace(local=None, dev=None)
    return str(version)


def release(dry_run=False, commit=True, pre=None, major=False, minor=False, patch=True):
    new_version = _bump_version(pre, major, minor, patch)
    print(f"Bump version to: {new_version}")
    if dry_run:
        subprocess.check_call(["towncrier", "--version", new_version, "--draft"])
    else:
        _replace_version(new_version)
        subprocess.check_call(["towncrier", "--yes", "--version", new_version])
        subprocess.check_call(["git", "add", "."])
        if commit:
            subprocess.check_call(["git", "commit", "-m", f"Release {new_version}"])
            subprocess.check_call(
                ["git", "tag", "-a", new_version, "-m", f"v{new_version}"]
            )
            subprocess.check_call(["git", "push"])
            subprocess.check_call(["git", "push", "--tags"])


def parse_args(argv=None):
    parser = argparse.ArgumentParser("release.py")

    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument(
        "--no-commit",
        action="store_false",
        dest="commit",
        default=True,
        help="Do not commit to Git",
    )
    group = parser.add_argument_group(title="version part")
    group.add_argument("--pre", help="Pre tag")
    group.add_argument("--major", action="store_true", help="Bump major version")
    group.add_argument("--minor", action="store_true", help="Bump minor version")
    group.add_argument("--patch", action="store_true", help="Bump patch version")

    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    release(args.dry_run, args.commit, args.pre, args.major, args.minor, args.patch)
