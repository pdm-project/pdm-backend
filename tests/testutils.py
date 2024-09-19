from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path


def get_tarball_names(path: Path) -> list[str]:
    with tarfile.open(path, "r:gz") as tar:
        return tar.getnames()


def get_wheel_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()
