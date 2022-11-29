# PDM-Backend

The build backend used by [PDM] that supports latest packaging standards.

[![PyPI](https://img.shields.io/pypi/v/pdm-backend?label=PyPI)](https://pypi.org/project/pdm-backend)
[![Tests](https://github.com/pdm-project/pdm-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/pdm-project/pdm-backend/actions/workflows/ci.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/pdm-project/pdm-backend/master.svg)](https://results.pre-commit.ci/latest/github/pdm-project/pdm-backend/master)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)

This is the backend for [PDM] projects that is fully-compatible with [PEP 517] spec, but you can also use it alone.
It reads the metadata of [PEP 621] format and coverts it to [Core metadata].

[pep 517]: https://www.python.org/dev/peps/pep-0517/
[pep 621]: https://www.python.org/dev/peps/pep-0621/
[Core metadata]: https://packaging.python.org/specifications/core-metadata/
[PDM]: https://pdm.fming.dev

## Links

- [Documentation](https://pdm-backend.fming.dev)
- [Changelog](https://github.com/pdm-project/pdm-backend/releases)
- [PDM Documentation][PDM]
- [PyPI](https://pypi.org/project/pdm-backend)
- [Discord](https://discord.gg/Phn8smztpv)

> **NOTE**
> This project has been renamed from `pdm-pep517` and the old project lives in the [legacy] branch.

[legacy]: https://github.com/pdm-project/pdm-backend/tree/legacy

## Sponsors

<p align="center">
    <a href="https://cdn.jsdelivr.net/gh/pdm-project/sponsors/sponsors.svg">
        <img src="https://cdn.jsdelivr.net/gh/pdm-project/sponsors/sponsors.svg"/>
    </a>
</p>

## License

This project is licensed under [MIT license](/LICENSE).
