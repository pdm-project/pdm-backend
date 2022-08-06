from __future__ import annotations

from typing import Any


class BuildError(RuntimeError):
    pass


class ProjectError(ValueError):
    pass


class MetadataError(ProjectError):
    def __init__(self, field: str, error: Any) -> None:
        message = f"{field}: {error}"
        super().__init__(message)


class PDMWarning(UserWarning):
    pass


class PEP621ValidationError(ProjectError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(errors)
        self.errors = errors
