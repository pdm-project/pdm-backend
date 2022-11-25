from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator, MutableMapping


class Table(MutableMapping[str, Any]):
    def __init__(self, data: dict[str, Any]) -> None:
        self.__data = data

    def __len__(self) -> int:
        return len(self.__data)

    def __iter__(self) -> Iterator[str]:
        return iter(self.__data)

    def __getitem__(self, __key: str) -> Any:
        return self.__data[__key]

    def __setitem__(self, __key: str, __value: Any) -> None:
        self.__data[__key] = __value

    def __delitem__(self, __key: str) -> None:
        del self.__data[__key]


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

    def __getitem__(self, __key: str) -> Path:
        return self.__data[self.__normalize_path(__key)]

    def __setitem__(self, __key: str, __value: Path) -> None:
        self.__data[self.__normalize_path(__key)] = __value

    def __delitem__(self, __key: str) -> None:
        del self.__data[__key]
