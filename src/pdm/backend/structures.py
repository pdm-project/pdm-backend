from __future__ import annotations

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
