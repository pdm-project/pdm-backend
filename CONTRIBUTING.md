# Contributing to PDM

First off, thanks for taking the time to contribute! Contributions include but are not restricted to:

* Reporting bugs
* Contributing to code
* Writing tests
* Writing documents

The following is a set of guidelines for contributing.

## A recommended flow of contributing to an Open Source project.

This guideline is for new beginners of OSS. If you are an experienced OSS developer, you can skip
this section.

1. First, fork this project to your own namespace using the fork button at the top right of the repository page.
2. Clone the **upstream** repository to local:
   ```bash
   $ git clone https://github.com/pdm-project/pdm-backend.git
   # Or if you prefer SSH clone:
   $ git clone git@github.com:pdm-project/pdm-backend.git
   ```
3. Add the fork as a new remote:
   ```bash
   $ git remote add fork https://github.com/yourname/pdm-backend.git
   $ git fetch fork
   ```
   where `fork` is the remote name of the fork repository.

**ProTips:**

1. Don't modify code on the main branch, the main branch should always keep in track with origin/main.

   To update main branch to date:

   ```bash
   $ git pull origin main
   # In rare cases that your local main branch diverges from the remote main:
   $ git fetch origin && git reset --hard main
   ```
2. Create a new branch based on the up-to-date main for new patches.
3. Create a Pull Request from that patch branch.

## Local development

Following [the guide][pdm-install] to install PDM on your machine, then install the development dependencies:

```bash
$ pdm sync
```

It will create a virtualenv at `$PWD/.venv` and install all dependencies into it.

[pdm-install]: https://pdm-project.org/latest/#installation

### Run tests

```bash
$ pdm run pytest -vv tests
```

The test suite is still simple and requires to be supplied, please help write more test cases.

### Code style

PDM uses `pre-commit` for linting, you need to install `pre-commit` first, then:

```bash
$ pre-commit install
$ pre-commit run --all-files
```

PDM uses `ruff` for code style and linting, if you are not following its
suggestions, the CI will fail and your Pull Request will not be merged.
