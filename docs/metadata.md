# Project metadata

The project metadata is stored in the `project` table in `pyproject.toml`, which is based on [PEP 621](https://peps.python.org/pep-0621/).

On top of that, we also support some additional features.

## Dynamic project version

`pdm-backend` can determine the version of the project dynamically. To do this, you need to leave the `version` field out from your `pyproject.toml` and add `version` to the list of `project.dynamic`:

```diff
[project]
...
- version = "0.1.0" remove this line
+ dynamic = ["version"]
```

Then in `[tool.pdm.version]` table, specify how to get the version info. There are three ways supported:

### Read from a static string in the given file path

```toml
[tool.pdm.version]
source = "file"
path = "mypackage/__init__.py"
```

In this way, the file MUST contain a line like:

```python
__version__ = "0.1.0" # Single quotes and double quotes are both OK, comments are allowed.
```

### Read from SCM tag, supporting `git` and `hg`

```toml
[tool.pdm.version]
source = "scm"
```

When building from a source tree where SCM is not available, you can use the env var `PDM_BUILD_SCM_VERSION` to pretend the version is set.

```bash
PDM_BUILD_SCM_VERSION=0.1.0 python -m build
```

You can specify another regex pattern to match the SCM tag, in which a `version` group is required:

```toml
[tool.pdm.version]
source = "scm"
tag_regex = '^(?:\D*)?(?P<version>([1-9][0-9]*!)?(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*((a|b|c|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?(\.dev(0|[1-9][0-9]*))?$)$'
```

### Get with a specific function

```toml
[tool.pdm.version]
source = "call"
getter = "mypackage.version.get_version"
```

You can also supply it with literal arguments:

```toml
getter = "mypackage.version.get_version('dev')"
```

## Writing dynamic version to file

You can instruct `pdm-backend` to write back the dynamic version to a file. It is supported for all sources but `file`.

```toml
[tool.pdm.version]
source = "scm"
write_to = "foo/version.txt"
```

By default, `pdm-backend` will just write the SCM version itself.
You can provide a template as a Python-formatted string to create a syntactically correct Python assignment:

```toml
[tool.pdm.version]
source = "scm"
write_to = "foo/_version.py"
write_template = "__version__ = '{}'"
```

!!! note
    The path in `write_to` is relative to the root of the wheel file, hence the `package-dir` part should be stripped.

!!! note
    `pdm-backend` will rewrite the whole file each time, so you can't have additional contents in that file.

## Variables expansion

### Environment variables

You can refer to environment variables in form of `${VAR}` in the dependency strings, both work for `dependencies` and `optional-dependencies`:

```toml
[project]
dependencies = [
    "foo @ https://${USERNAME}:${PASSWORD}/mypypi.org/packages/foo-0.1.0-py3-none-any.whl"
]
```

When you build the project, the variables will be expanded with the current values of the environment variables.

### Relative paths

You can add a dependency with the relative paths to the project root. To do this, `pdm-backend` provides a special variable `${PROJECT_ROOT}`
to refer to the project root, and the dependency must be defined with the `file://` URL:

```toml
[project]
dependencies = [
    "foo @ file:///${PROJECT_ROOT}/foo-0.1.0-py3-none-any.whl"
]
```

To refer to a package beyond the project root:

```toml
[project]
dependencies = [
    "foo @ file:///${PROJECT_ROOT}/../packages/foo-0.1.0-py3-none-any.whl"
]
```

!!! note
    The triple slashes `///` is required for the compatibility of Windows and POSIX systems.

!!! note
    The relative paths will be expanded into the absolute paths on the local machine. So it makes no sense to include them in a distribution, since others who install the package will not have the same paths.
