from __future__ import annotations

import os
from collections.abc import Iterator, MutableMapping
from pathlib import Path
from typing import Any


class Table(MutableMapping[str, Any]):
    def __init__(self, data: dict[str, Any]) -> None:
        self.__data = data

    def __len__(self) -> int:
        return len(self.__data)

    def __iter__(self) -> Iterator[str]:
        return iter(self.__data)

    def __getitem__(self, key: str, /) -> Any:
        return self.__data[key]

    def __setitem__(self, key: str, value: Any, /) -> None:
        self.__data[key] = value

    def __delitem__(self, key: str, /) -> None:
        del self.__data[key]


class FileMap(MutableMapping[str, Path]):
    def __init__(self) -> None:
        self.__data: dict[str, Path] = {}

    def __normalize_path(self, path: str) -> str:
        path = os.path.normpath(path)
        if os.sep == "\\":
            path = path.replace("\\", "/")
        return path

    def __len__(self) -> int:
        return len(self.__data)

    def __iter__(self) -> Iterator[str]:
        return iter(self.__data)

    def __getitem__(self, key: str, /) -> Path:
        return self.__data[self.__normalize_path(key)]

    def __setitem__(self, key: str, value: Path, /) -> None:
        self.__data[self.__normalize_path(key)] = value

    def __delitem__(self, key: str, /) -> None:
        del self.__data[key]
