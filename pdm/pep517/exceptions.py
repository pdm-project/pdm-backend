from typing import Any, List


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
    def __init__(self, errors: List[str]) -> None:
        super().__init__(errors)
        self.errors = errors
