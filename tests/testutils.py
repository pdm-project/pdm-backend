import tarfile
import zipfile
from pathlib import Path
from typing import List


def get_tarball_names(path: Path) -> List[str]:
    with tarfile.open(path, "r:gz") as tar:
        return tar.getnames()


def get_wheel_names(path: Path) -> List[str]:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()
