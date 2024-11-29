# Build configurations

All build configurations are stored under `tool.pdm.build` table.

## Specify the package files

The PDM backend supports conventional project layouts, eliminating the need for configuration in most projects.
Additionally, you can customize which files to include or exclude using various configurations.
Let's take a look at some examples.

### The common package layout

```
.
├── pyproject.toml
├── mypackage
│   ├── __init__.py
│   └── lib.py
└── tests
    └── test_lib.py
```

Build this project and you will get the distributions with the following contents:

=== "mypackage-0.1.0.tar.gz"

    ```
    pyproject.toml
    PKG-INFO
    mypackage/__init__.py
    mypackage/lib.py
    tests/test_lib.py
    ```

=== "mypackage-0.1.0-py3-none-any.whl"

    ```
    mypackage/__init__.py
    mypackage/lib.py
    mypackage-0.1.0.dist-info/...
    ```

Basically, a source distribution should contain all the files required to build or test the package. Typically, a wheel distribution
should also be built from that. On the contrary, the files in a wheel distribution will be copied to the site-packages directory as-is.
So you can notice the `tests/` are include by a source distribution but not by a wheel.

When the wheel is installed, there will be the following files on your local disk:

```
.../site-packages/mypackage/__init__.py
.../site-packages/mypackage/lib.py
.../site-packages/mypackage-0.1.0.dist-info/...
```

So that you can directly do `import mypackage` in your code.

For a wheel, there are some special handlings for the console scripts and data files,
read the details in [Python Packaging User Guide](https://packaging.python.org/en/latest/specifications/binary-distribution-format/).

!!! note "More than one top packages"
    If there are more than one top packages in your project, they will be included in the distribution as well.
    A directory is considered as a top package if it contains an `__init__.py` file.
    All this can be achieved without any build configuration.

### The module files layout

If there is no package in your project but instead only module files, these files will be included in the distribution.
The project layout can be like the following:

```
.
├── pyproject.toml
├── mymodule.py
└── tests
    └── test_mymodule.py
```

### Include or exclude files

By default, Python files under the project root will be included only when there is no package found. You can change this by
specifying the `includes` and `excludes` settings.

```toml
[tool.pdm.build]
includes = ["mypackage/", "script.py"]
```

Note that this is uncommon because it will place both `mypackage/` and `script.py` under the `site-packages` directory when installed.
However, the build scripts are required by a source distribution to build the package, and you don't want them to be installed.
In this case, use the `source-includes` setting instead:

```toml
[tool.pdm.build]
source-includes = ["scripts/", "tests/"]
```
By default, test files under `tests`, if found, are included by sdist and excluded by other formats.
These paths can be overridden by specifying `source-includes` manually.

Similarly, the `excludes` config also accepts a list of relative paths or glob patterns, and the matched files will not be packaged
in to the distribution.

### Include files in a namespace package

A [PEP 420](https://www.python.org/dev/peps/pep-0420/) namespace package is a package that is split across multiple directories on the filesystem. It is a directory without an `__init__.py` file. For example, this is a Python package with nested namespace packages:

```
basepackage/
  somenamespace/
    my_namespace_package/
      __init__.py
      ...
pyproject.toml
```

PDM-Backend doesn't collect the files in the namespace packages automatically. Instead, you have to specify it in the `includes` setting manually:

```toml
[tool.pdm.build]
includes = ["basepackage/"]
```

### The src layout

The src layout is also a common project layout which places all the python source files under a `src` directoy. PDM-backend also detects this automatically. Given the following project layout:

```
.
├── pyproject.toml
├── src
│   └── mypackage
│       ├── __init__.py
│       └── lib.py
└── tests
```

The built distribution will be:

=== "mypackage-0.1.0.tar.gz"
    ```
    pyproject.toml
    src/mypackage/__init__.py
    src/mypackage/lib.py
    tests/test_lib.py
    ```

=== "mypackage-0.1.0-py3-none-any.whl"
    ```
    mypackage/__init__.py
    mypackage/lib.py
    mypackage-0.1.0.dist-info/...
    ```

You can see the files are remapped in the wheel distribution but keep the same in the source distribution.

PDM-backend enables the src layout when it finds a `src/` directory. But you can also specify the directory name by `package-dir` configuration:

```
[tool.pdm.build]
package-dir = "mysrc"
```

The default value is `src` if `src/` is found and `.` otherwise.

### Priority of includes and excludes

If a file is covered by both `includes` and `excludes`, the one with the more path parts and less wildcards in the pattern wins,
otherwise `excludes` takes precedence if the length is the same.

For example, given the following configuration:

```toml
includes = ["src"]
excludes = ["**/*.json"]
```

`src/foo/data.json` will be **excluded** since the pattern in `excludes` has more path parts, however, if we change the configuration to:

```toml
includes = ["src", "src/foo/data.json"]
excludes = ["**/*.json"]
```

the same file will be **included** since it is covered by `includes` with a more specific path.

### Default includes and excludes

If neither `includes` and `excludes` is specified, the backend can determine them following the rules as below:

- If top-level packages are found under `package-dir`, they will be included, together with any data files inside.
- Otherwise, all top-level `*.py` files under `package-dir` will be included.
- See `source-includes` for further includes.

!!! note
    Specifying `includes` and `excludes` will **override** their default values, so you need to include the package directories manually.
    `*.pyc`, `__pycache__/` and `build/` are always excluded.


### Wheel data files

You can include additional files that are not normally installed inside site-packages directory, with `tool.pdm.build.wheel-data` table:

```toml
[tool.pdm.build.wheel-data]
# Install all files under scripts/ to the $prefix/bin directory.
scripts = ["scripts/*"]
# Install all *.h files under headers/ (recursively) to the $prefix/include directory,
# flattening all files into one directory:
# headers/folder1/file1.h -> $prefix/include/file1.h
# headers/folder2/file2.h -> $prefix/include/file2.h
include = [{path = "headers/**/*.h"}]
```

The keys are the name of the install scheme, and should be amongst `scripts`, `purelib`, `platlib`, `include`, `platinclude` and `data`.
The values should be lists of items, which may contain the following attributes:

- `path`: The path pattern to match the files to be included.
- `relative-to`: if specified, the relative paths of the matched files will be calculated based on this directory,
otherwise the files will be flattened and installed directly under the scheme directory.

In both attributes, you can use `${BUILD_DIR}` to refer to the build directory.

These files will be packaged into the `{name}-{version}.data/{scheme}` directory in the wheel distribution.

Advanced examples:

```toml
[tool.pdm.build.wheel-data]
# Install all *.h files under headers/ (recursively) to the $prefix/include directory,
# keeping the directory structure (thanks to relative-to).
# We make the destination paths relative to "headers"
# so that "headers" does not appear in the destination paths:
# headers/folder1/file1.h -> $prefix/include/folder1/file1.h
include = [{path = "headers/**/*.h", relative-to = "headers/"}]
# Install all files under share/ (recursively) to the $prefix/data directory,
# keeping the directory structure (thanks to relative-to).
# We make the destination paths relative to "."
# to preserve the exact same directory structure in the destination:
# share/man/man1/project.1 -> $prefix/data/share/man/man1/project.1
data = [{path = "share/**/*", relative-to = "."}]
```

!!! warning
    If you use [pyproject-build](https://github.com/pypa/build) to build your distributions,
    note that its default behavior is to build the wheel from the contents of the sdist.
    It means that if you don't include your data files to the sdist, they won't be included in the wheel.
    To disable this default mode of pyproject-build, explicitely pass it the `-w`, `--wheel` flag.
    But to be safe, and allow others to build your project with `pyproject-build` or `python -m build`,
    you should [include your data files to the sdist](#include-or-exclude-files), for example with:

    ```toml
    [tool.pdm.build]
    package-dir = "src"
    source-includes = ["share"]

    [tool.pdm.build.wheel-data]
    data = [
        {path = "share/**/*", relative-to = "."},
    ]
    ```
    

## Local build hooks

You can specify a custom script to be executed before the build process, which can be used to generate files or modify the metadata.
A file named `pdm_build.py` under the project root will be detected as custom hook script automatically, or you can specifiy the name
via `custom-hook` setting:

```toml
[tool.pdm.build]
custom-hook = "build.py"
```

**Default value**: `pdm_build.py`

### Run setuptools

Due the lack of ability to build C extensions, `pdm-backend` allow users to call `setuptools` in an auto-generated `setup.py` from the
project. This is enabled by setting `run-setuptools` to `true`:

```toml
[tool.pdm.build]
run-setuptools = true
```

**Default value**: `false`

The hook function `pdm_build_update_setup_kwargs` will be called to modify the arguments passed to `setup()` function as you desire.

Read the [hooks document](./hooks.md) about the details of the hook functions.

## `is-purelib`

By default, `pdm-backend` produces non platform-specific wheels, with tag `py3-none-any`. But if `run-setuptools` is `true`, the built wheel
will be platform-specific. You can override this behavior by setting `is-purelib` to `true` or `false` explicitly:

```toml
[tool.pdm.build]
is-purelib = true
```

## Choose the editable build format

`pdm-backend` supports two ways to build an [editable wheel][PEP 660], `path` and `editables`, with the former being the default. It can be changed with `editable-backend` setting:

[PEP 660]: https://www.python.org/dev/peps/pep-0660/

```toml
[tool.pdm.build]
editable-backend = "editables"
```

**Default value**: `path`

### `path`

In this approach, the editable build will be very similar to the legacy format generated by `setuptools`. A `.pth` file containing the parent path of the packages will be installed into the site-packages directory.

### `editables`

If you choose this approach, the backend will install a proxy module which redirects the import statements to the real location of the package, which is powered by the [editables] package.

[editables]: https://pypi.org/project/editables

## Build config settings

Some build frontends such as [build] and [pdm] supports passing options from command-line to the backend. `pdm-backend` supports the following config settings:

- `--python-tag=<tag>` Override the python implementation compatibility tag(e.g. `cp37`, `py3`, `pp3`)
- `--py-limited-api=<abi>` Python tag (`cp32`|`cp33`|`cpNN`) for abi3 wheel tag
- `--plat-name=<plat>` Override the platform name(e.g. `win_amd64`, `manylinux2010_x86_64`)
- `--build-number=<build-number>` Build number for this particular version. As specified in PEP-0427, this must start with a digit.
- `no-clean-build` Don't clean the build directory before the build starts, this can also work by setting env var `PDM_BUILD_NO_CLEAN` to `1`.

For example, you can supply these options with [build]:

```bash
python -m build --sdist --wheel --outdir dist/ --config-setting="--python-tag=cp37" --config-setting="--plat-name=win_amd64"
```

## Environment variables

- `SOURCE_DATE_EPOCH`: Set the timestamp(seconds) of the zipinfo in the wheel for reproducible builds. The default date is 2016/01/01.

[build]: https://pypi.org/project/build
[pdm]: https://pypi.org/project/pdm
