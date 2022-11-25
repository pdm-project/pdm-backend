from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pdm.backend.hooks.base import Context

logger = logging.getLogger("hooks")


class BuildHook:
    def __init__(self, name: str = "2") -> None:
        self.name = name

    def pdm_build_clean(self, context: Context) -> None:
        logger.info("Hook%s build clean called", self.name)

    def pdm_build_initialize(self, context: Context) -> None:
        logger.info("Hook%s build initialize called", self.name)

    def pdm_build_update_files(self, context: Context, files: dict[str, Path]) -> None:
        logger.info("Hook%s build update files called", self.name)

    def pdm_build_finalize(self, context: Context, artifact: Path) -> None:
        logger.info("Hook%s build finalize called", self.name)


# Hook instance
hook3 = BuildHook("3")
