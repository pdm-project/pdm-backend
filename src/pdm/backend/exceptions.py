from __future__ import annotations


class BuildError(RuntimeError):
    pass


class ProjectError(ValueError):
    pass


class PDMWarning(UserWarning):
    pass


class ValidationError(ProjectError):
    def __init__(self, summary: str, details: str) -> None:
        super().__init__(summary)
        self.summary = summary
        self.details = details

    def __str__(self) -> str:
        return f"{self.summary}\n{self.details}"
