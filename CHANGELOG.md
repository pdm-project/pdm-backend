Release v0.5.9 (2021-03-24)
---------------------------

### Bug Fixes

- Fix a parsing error on reStructuredText description due to missing indentation for empty lines. [#11](https://github.com/frostming/pdm-pep517/issues/11)
- Fix the WHEEL writer to report the correct wheel generator. [#12](https://github.com/frostming/pdm-pep517/issues/12)


Release v0.5.8 (2021-03-16)
---------------------------

### Bug Fixes

- Fix a bug that platform-specific tags cannot be generated correctly.

Release v0.5.7 (2021-03-05)
---------------------------

### Bug Fixes

- Fix a bug that python modules under `src` directory without a parent package are not included in the built results nor `py_modules` key in `setup.py`. [#9](https://github.com/frostming/pdm-pep517/issues/9)


Release v0.5.6 (2021-02-08)
---------------------------

### Bug Fixes

- Don't include redundant `Homepage` in the core metadata.

Release v0.5.5 (2021-02-05)
---------------------------

### Bug Fixes

- Rewrite the import statements in vendored packages to avoid namespace conflicts.

Release v0.5.4 (2021-01-26)
---------------------------

### Bug Fixes

- Automatically exclude `tests` directory from the build results when not specified.

Release v0.5.3 (2021-01-26)
---------------------------

### Bug Fixes

- Fix a bug that default settings include many misc directories that are not Python packages.

Release v0.5.2 (2021-01-24)
---------------------------

### Bug Fixes

- Fix a bug that `__pypackages__` gets included in the build files unexpectedly.

Release v0.5.0 (2021-01-11)
---------------------------

### Features & Improvements

- Support PEP 420 implicit namespace packages [#7](https://github.com/frostming/pdm-pep517/issues/7)


Release v0.4.0 (2020-12-24)
---------------------------

### Features & Improvements

- Autogen trove classifiers based on `requires-python` and `license`. [#6](https://github.com/frostming/pdm-pep517/issues/6)


Release v0.3.3 (2020-12-22)
---------------------------

### Features & Improvements

- Auto convert legacy metadata format for backward compatibility. [#5](https://github.com/frostming/pdm-pep517/issues/5)


Release v0.3.2 (2020-12-21)
---------------------------

### Bug Fixes

- Fix setup.py encoding issue. [#4](https://github.com/frostming/pdm-pep517/issues/4)


Release v0.3.0 (2020-12-21)
---------------------------

### Features & Improvements

- Support [PEP 621](https://www.python.org/dev/peps/pep-0621/) project metadata specification. [#4](https://github.com/frostming/pdm-pep517/issues/4)
