from __future__ import annotations

import logging
from pathlib import Path

from pdm.backend.hooks.base import Context

logger = logging.getLogger("hooks")


def pdm_build_clean(context: Context) -> None:
    logger.info("Hook4 build clean called")


def pdm_build_initialize(context: Context) -> None:
    logger.info("Hook4 build initialize called")


def pdm_build_update_files(context: Context, files: dict[str, Path]) -> None:
    logger.info("Hook4 build update files called")


def pdm_build_finalize(context: Context, artifact: Path) -> None:
    logger.info("Hook4 build finalize called")
