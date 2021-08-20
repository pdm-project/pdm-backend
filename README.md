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

Besides of the standard fields specified in PEP 621, PDM-PEP517 honors some other settings to change the build behavior. They should be defined under `[tool.pdm]` table:

```toml
[tool.pdm]
package-dir = "src"  # Similar to setuptools package_dir option
includes = []        # File patterns to include, the paths are relative to the project root.
excludes = []        # File patterns to exclude, the paths are relative to the project root.
source-includes = [] # File patterns to include in source distribution and exclude in wheel distribution
```
You don't have to specify all of them, PDM-PEP517 can also derive these fields smartly, based on some best practices of Python packaging.

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

## Support PEP 660 for setuptools backend

If your project need to support editable wheel build([PEP 660](https://www.python.org/dev/peps/pep-0660/)) and is backed by `setuptools`, you can write the following in `pyproject.toml`:

```toml
[build-system]
requires = ["pdm-pep517[setuptools]"]
build-backend = "pdm.pep517.setuptools"
```

PDM will infer the backend correctly so you don't need to do it.

## License

This project is licensed under [MIT license](/LICENSE).
