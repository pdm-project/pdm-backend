# build.py
from setuptools.command.build_py import build_py


class MyBuild(build_py):
    pass


def build(setup_kwargs):
    setup_kwargs.update(cmdclass={"build_py": MyBuild})
