# PDM-PEP517

Yet another [PEP 517][1] backend.

[![PyPI](https://img.shields.io/pypi/v/pdm-pep517?label=PyPI)](https://pypi.org/project/pdm-pep517)
[![Tests](https://github.com/pdm-project/pdm-pep517/actions/workflows/ci.yml/badge.svg)](https://github.com/pdm-project/pdm-pep517/actions/workflows/ci.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/pdm-project/pdm-pep517/master.svg)](https://results.pre-commit.ci/latest/github/pdm-project/pdm-pep517/master)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)

This is the backend for [PDM](https://pdm.fming.dev) projects, while you can also use it alone.
It reads the metadata of [PEP 621][2] format and coverts it to [Core metadata][3].

[1]: https://www.python.org/dev/peps/pep-0517/
[2]: https://www.python.org/dev/peps/pep-0621/
[3]: https://packaging.python.org/specifications/core-metadata/

## Use as PEP 517 build backend

Edit your `pyproject.toml` as follows:

```toml
[build-system]
requires = ["pdm-pep517"]
build-backend = "pdm.pep517.api"
```

## Tool specific settings

Besides of the standard fields specified in PEP 621, PDM-PEP517 honors some other settings to change the build behavior. They should be defined under `[tool.pdm.build]` table:

```toml
[tool.pdm.build]
# Specify where the Python packages live.
package-dir = "src"
# File patterns to include, the paths are relative to the project root.
includes = []
# File patterns to exclude, the paths are relative to the project root.
excludes = []
# File patterns to include in source distribution and exclude in wheel distribution.
source-includes = []
# An extra script to populate the arguments of `setup()`, one can build C extensions with this script. Or a custom build() function to generate files.
setup-script = "build.py"
# If true, the setup-script will run in a generated `setup.py` file.
run-setuptools = false
# Override the Is-Purelib value in the wheel.
is-purelib = true
# Change the editable-backend: path(default) or editables
editable-backend = "editables"
```

You don't have to specify all of them, PDM-PEP517 can also derive these fields smartly, based on some best practices of Python packaging.

## Dynamic project version

`pdm-pep517` can also determine the version of the project dynamically. To do this, you need to leave the `version` field out from your `pyproject.toml` and add `dynamic = ["version"]`:

```diff
[project]
...
- version = "0.1.0" remove this line
+ dynamic = ["version"]
```

Then in `[tool.pdm.version]` table, specify how to get the version info. There are two ways supported:

1. Read from a static string in the given file path:

```toml
[tool.pdm.version]
source = "file"
path = "mypackage/__init__.py"
```

In this way, the file MUST contain a line like:

```python
__version__ = "0.1.0" # Single quotes and double quotes are both OK, comments are allowed.
```

2. Read from SCM tag, supporting `git` and `hg`:

```toml
[tool.pdm.version]
source = "scm"
```

When building from a source tree where SCM is not available, you can use the env var `PDM_PEP517_SCM_VERSION` to pretend the version is set.

```bash
PDM_PEP517_SCM_VERSION=0.1.0 python -m build
```

## Writing SCM version to file

You can instruct PDM-PEP517 to write back the dynamic version fetched from SCM to a file:

```toml
[tool.pdm.version]
source = "scm"
write_to = "foo/version.txt"
```

By default, PDM-PEP517 will just write the SCM version itself.
You can provide a template as a Python-formatted string to create a syntactically correct Python assignment:

```toml
[tool.pdm.version]
source = "scm"
write_to = "foo/_version.py"
write_template = "__version__ = '{}'"
```

Note that PDM-PEP517 will rewrite the whole file each time, so you can't have additional contents in that file.

## Custom Build Script

With custom build script, you can call other tools to generates files to be included in the wheel.
Just set the `setup-script` field under `[tool.pdm.build]` table to the path of the script.

In the script, you expose a function named `build`, which takes two arguments:

- `src`(str): the path of the source directory
- `dst`(str): the path of the destination directory

Example:

```python

def build(src, dst):
    with open(os.path.join(dst, "myfile.txt"), "w") as f:
        # Put a file in the wheel
        f.write("Hello World!")
```
Note that the generated file hierarchy will be preserved in the wheel: `$dst/myfile.txt` -> `$wheel_root/myfile.txt`.

When `run-setuptools` is `true`, the `build` function will be called in a generated `setup.py` file, with the setup parameters as the only argument.

Example:

```python

def build(setup_params):
    # add ext_modules to the setup() arguments
    setup_parms.update(ext_modules=[Extension("myextension", ["myextension.c"])])
```

The will result in a `setup()` call like following:

```python
setup(
    name="mypackage",
    # Other metadata fields
    ext_modules=[Extension("myextension", ["myextension.c"])],
)
```

**By default, when `setup-script` is set, the resulted wheel will be platform-specific, but you can override this behavior by setting `is-purelib` to `false`**

## Supported config settings

`pdm-pep517` allows passing `config_settings` to modify the build behavior. It use the same option convention as `python setup.py bdist_wheel`.

```
--python-tag
    Override the python implementation compatibility tag(e.g. cp37, py3, pp3)
--py-limited-api
    Python tag (cp32|cp33|cpNN) for abi3 wheel tag
--plat-name
    Override the platform name(e.g. win_amd64, manylinux2010_x86_64)
```

For example, you can supply these options with [build](https://pypi.org/project/build/):

```bash
python -m build --sdist --wheel --outdir dist/ --config-setting="--python-tag=cp37" --config-setting="--plat-name=win_amd64"
```

`pip` doesn't support passing `config_settings` yet, please stick to `build` as the recommended frontend.

## License

This project is licensed under [MIT license](/LICENSE).
