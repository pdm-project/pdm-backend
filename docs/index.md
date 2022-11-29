# PDM-Backend

[![PyPI](https://img.shields.io/pypi/v/pdm-backend?label=PyPI)](https://pypi.org/project/pdm-backend)
[![Tests](https://github.com/pdm-project/pdm-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/pdm-project/pdm-backend/actions/workflows/ci.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/pdm-project/pdm-backend/master.svg)](https://results.pre-commit.ci/latest/github/pdm-project/pdm-backend/master)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)

PDM-Backend is a build backend that supports the latest packaging standards, which includes:

- [PEP 517] Build backend API
- [PEP 621] Project metadata
- [PEP 660] Editable build backend

[PEP 517]: https://www.python.org/dev/peps/pep-0517/
[PEP 621]: https://www.python.org/dev/peps/pep-0621/
[PEP 660]: https://www.python.org/dev/peps/pep-0660/

## Quick start

To use it as PEP 517 build backend, edit your `pyproject.toml` as below:

```toml
[build-system]
requires = ["pdm-backend"]
build-backend = "pdm.backend"
```

It is recommended to use [PDM] to manage your project, which will automatically generate the above configuration for you.

[PDM]: https://pdm.fming.dev

Write the project metadata in `pyproject.toml` in [PEP 621] format:

```toml
[project]
name = "my-project"
version = "0.1.0"
description = "A project built with PDM-Backend"
authors = [{name = "John Doe", email="me@johndoe.org"}]
dependencies = ["requests"]
requires-python = ">=3.8"
readme = "README.md"
license = {text = "MIT"}
```

Then run the build command to build the project as wheel and sdist:

=== "PDM"

    ```bash
    pdm build
    ```

=== "build"

    ```bash
    python -m build
    # Or
    pyproject-build
    ```

Read the corresponding documentation sections for more details:

- [Metadata](./metadata.md) for how to write the project metadata
- [Build configuration](./build_config.md) for customizing the build process.

## Migrate from `pdm-pep517`

`pdm-backend` is the successor of `pdm-pep517`. If you are using the latter for your project, read the [migration guide](./migration.md) to migrate to `pdm-backend`.

## Sponsors

Thanks to all the individuals and organizations who sponsor PDM project!

<p align="center">
    <a href="https://cdn.jsdelivr.net/gh/pdm-project/sponsors/sponsors.svg">
        <img src="https://cdn.jsdelivr.net/gh/pdm-project/sponsors/sponsors.svg"/>
    </a>
</p>
