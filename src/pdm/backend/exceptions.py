from __future__ import annotations


class BuildError(RuntimeError):
    pass


class ConfigError(ValueError):
    pass


class PDMWarning(UserWarning):
    pass


class ValidationError(ConfigError):
    def __init__(self, summary: str, key: str | None = None) -> None:
        super().__init__(summary)
        self.key = key

    def __str__(self) -> str:
        prefix = f"{self.key}: " if self.key else ""
        return f"{prefix}{self.args[0]}"
