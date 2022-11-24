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

    def __post_init__(self):
        self.root = self.config.root


class BuildHookInterface(Protocol):
    """The interface definition for build hooks.

    Custom hooks can implement part of the methods to provide corresponding abilities.
    """

    def initalize(self, context: Context) -> None:
        """This hook will be called before the build starts,
        any updates to the context object will be seen by the following processes.
        """
        ...

    def update_file_list(self, context: Context, files: dict[str, str]) -> None:
        """Passed in the current file mapping of {file_path: rel_path}
        for hooks to update
        """
        ...

    def finalize(self, context: Context, artifact: Path) -> None:
        """This hook will be called after the build is done,
        the artifact is the path to the built artifact.
        """
        ...

    def update_setup_kwargs(self, context: Context, kwargs: dict[str, Any]) -> None:
        """Passed in the setup kwargs for hooks to update"""
        ...
