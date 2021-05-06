# PDM-PEP517

Yet another [PEP 517][1] backend.

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

## Supported config settings

`pdm-pep517` allows passing `config_settings` to modify the build behavior. It use the same option convention as `python setup.py bdist_wheel`.

```
--python-tag: Override the python implementation compatibility tag(e.g. cp37, py3, pp3)
--py-limited-api: Python tag (cp32|cp33|cpNN) for abi3 wheel tag
--plat-name: Override the platform name(e.g. win_amd64, manylinux2010_x86_64)
```

For example, you can supply these options with [build](https://pypi.org/project/build/):

```bash
python -m build --sdist --wheel --outdir dist/ --config-setting="--python-tag=cp37" --config-setting="--plat-name=win_amd64"
```

`pip` doesn't support passing `config_settings` yet, please stick to `build` as the recommended frontend.

## License

This project is licensed under [MIT license](/LICENSE).
