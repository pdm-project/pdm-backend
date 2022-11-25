from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pdm.backend.config import Config

if TYPE_CHECKING:
    from typing import Protocol
else:
    Protocol = object


@dataclasses.dataclass()
class Context:
    """The context object for the build hook,
    which contains useful information about the building process.
    Custom hooks can also change the values of attributes or
    assign arbitrary attributes to this object.
    """

    # The project root directory
    root: Path
    # The parsed pyproject.toml as a Config object
    config: Config
    # The target to build, one of "sdist", "wheel", "editable"
    target: str
    # The build directory for storing files generated during the build
    build_dir: Path
    # The directory to store the built artifacts
    dist_dir: Path
    # The config settings passed to the hook
    config_settings: dict[str, str]
    # The extra args passed to the build method
    kwargs: dict[str, Any]

    def ensure_build_dir(self) -> None:
        """Ensure the build directory exists."""
        if not self.build_dir.exists():
            self.build_dir.mkdir(mode=0o700, parents=True)


class BuildHookInterface(Protocol):
    """The interface definition for build hooks.

    Custom hooks can implement part of the methods to provide corresponding abilities.
    """

    def is_enabled(self, context: Context) -> bool:
        """Return True if the hook is enabled for the current build"""
        ...

    def pdm_build_clean(self, context: Context) -> None:
        """An optional clean step which will be called before the build starts"""
        ...

    def pdm_build_initialize(self, context: Context) -> None:
        """This hook will be called before the build starts,
        any updates to the context object will be seen by the following processes.
        """
        ...

    def pdm_build_update_files(self, context: Context, files: dict[str, Path]) -> None:
        """Passed in the current file mapping of {relpath: path}
        for hooks to update
        """
        ...

    def pdm_build_finalize(self, context: Context, artifact: Path) -> None:
        """This hook will be called after the build is done,
        the artifact is the path to the built artifact.
        """
        ...

    def pdm_build_update_setup_kwargs(
        self, context: Context, kwargs: dict[str, Any]
    ) -> None:
        """Passed in the setup kwargs for hooks to update"""
        ...
