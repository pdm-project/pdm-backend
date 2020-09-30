# PDM-PEP517

The PEP 517 support for [PDM](https://pdm.fming.dev)

_This is a **WIP** project_

Authored by frostming

## Use as PEP 517 build backend

Edit your `pyproject.toml` as follows:

```toml
[build-system]
requires = ["pdm-pep517"]
build-backend = "pdm.pep517.api"
```
