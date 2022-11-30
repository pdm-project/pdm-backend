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

    Attributes:
        root: The project root directory
        config: The parsed pyproject.toml as a Config object
        target: The target to build, one of "sdist", "wheel", "editable"
        build_dir: The build directory for storing files generated during the build
        dist_dir: The directory to store the built artifacts
        config_settings: The config settings passed to the hook
        kwargs: The extra args passed to the build method
    """

    root: Path
    config: Config
    target: str
    build_dir: Path
    dist_dir: Path
    config_settings: dict[str, str]
    kwargs: dict[str, Any]

    def ensure_build_dir(self) -> None:
        """Create if the build dir doesn't exist"""
        if not self.build_dir.exists():
            self.build_dir.mkdir(mode=0o700, parents=True)


class BuildHookInterface(Protocol):
    """The interface definition for build hooks.

    Custom hooks can implement part of the methods to provide corresponding abilities.
    """

    def pdm_build_hook_enabled(self, context: Context) -> bool:
        """Return True if the hook is enabled for the current build and context

        Parameters:
            context: The context for this build
        """
        ...

    def pdm_build_clean(self, context: Context) -> None:
        """An optional clean step which will be called before the build starts

        Parameters:
            context: The context for this build
        """
        ...

    def pdm_build_initialize(self, context: Context) -> None:
        """This hook will be called before the build starts,
        any updates to the context object will be seen by the following processes.
        It is recommended to modify the metadata in this hook.

        Parameters:
            context: The context for this build
        """
        ...

    def pdm_build_update_files(self, context: Context, files: dict[str, Path]) -> None:
        """Passed in the current file mapping of {relpath: path}
        for hooks to update.

        Parameters:
            context: The context for this build
            files: The file mapping to be included in the build artifact, where the key
                is the relpath inside the artifact(wheel or tarball) and the value is
                the local path to the file.
        """
        ...

    def pdm_build_finalize(self, context: Context, artifact: Path) -> None:
        """This hook will be called after the build is done,
        the artifact is the path to the built artifact.

        Parameters:
            context: The context for this build
            artifact: The path to the built artifact
        """
        ...

    def pdm_build_update_setup_kwargs(
        self, context: Context, kwargs: dict[str, Any]
    ) -> None:
        """Passed in the setup kwargs for hooks to update.

        Parameters:
            context: The context for this build
            kwargs: The arguments to be passed to the setup() function

        Note:
            This hook will be called in the subprocess of running setup.py.
            Any changes made to the context won't be written back.
        """
        ...
