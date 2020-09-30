import os
import subprocess

from .base import Builder, BuildError
from .utils import make_setuptools_shim_args, to_filename


class EditableBuilder(Builder):
    def _find_egg_info(self, directory):
        filename = next(
            (
                f
                for f in os.listdir(directory)
                if f.endswith(".egg-info")
                and f[:-9].lower() == to_filename(self.meta.project_name).lower()
            ),
            None,
        )
        if not filename:
            raise BuildError("No egg info is generated.")
        return filename

    def build(self, build_dir: str, **kwargs) -> str:
        # Ignore destination since editable builds should be build locally
        setup_py_path = self.ensure_setup_py()
        args = make_setuptools_shim_args(setup_py_path.as_posix())
        args.extend(["egg_info", "--egg-base", build_dir])
        self.logger.info("Building egg info...")
        proc = subprocess.run(args, capture_output=True)
        self.logger.debug(proc.stdout)
        if proc.returncode:
            raise BuildError(f"Error occurs when running {args}:\n{proc.stderr}")
        return self._find_egg_info(build_dir)
