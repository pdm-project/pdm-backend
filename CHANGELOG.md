## Release v1.0.4 (2022-08-06)
### Bug Fixes

- Fix a bug of editable install not reading `run-setuptools = false` config. [#107](https://github.com/frostming/pdm-pep517/issues/107)
- Put the long description in the body as specified by Metadata Version 2.1 [#109](https://github.com/frostming/pdm-pep517/issues/109)
- Overwrite the existing files in the custom build stage of `WheelBuilder`. [#114](https://github.com/frostming/pdm-pep517/issues/114)


## Release v1.0.2 (2022-07-10)
### Bug Fixes

- Ensure the license is a file. Also add `LICENSES/*` to the default search patterns, as specified by [REUSE spec](https://reuse.software/spec/). [#105](https://github.com/frostming/pdm-pep517/issues/105)
- Throw a better error message when a malformed requirement is being parsed. [#106](https://github.com/frostming/pdm-pep517/issues/106)


## Release v1.0.1 (2022-07-03)

### Bug Fixes

- Fix a compatibility issue that `run_setuptools` defaults to True for old build configuration.

## Release v1.0.0 (2022-06-25)

No significant changes.

## Release v1.0.0a1 (2022-06-22)

### Bug Fixes

- Emit `UserWarning` for deprecated settings.

## Release v1.0.0a0 (2022-06-22)

### Features & Improvements

- Allow writing dynamic version from `scm` source to a file. [#94](https://github.com/frostming/pdm-pep517/issues/94)
- The dynamic version table fields are renamed: `{from = ...}` to `{source = "file", path = ...}` and `{use_scm = true}` to `{source = "scm"}`. [#95](https://github.com/frostming/pdm-pep517/issues/95)
- Support custom build script, a script containing a function named `build` that takes (src, dst) as the arguments. When `run-setuptools` is `true`, the `build` function will be called in a generated `setup.py` file, with the setup parameters as the only argument. [#98](https://github.com/frostming/pdm-pep517/issues/98)

### Removals and Deprecations

- `includes`, `excludes`, `source-includes`, `package-dir`, `is-purelib`, `editable-backend` are moved to `[tool.pdm.build]` table. `build` field is renamed to `setup-script` under `[tool.pdm.build]` table. [#96](https://github.com/frostming/pdm-pep517/issues/96)

## Release v0.12.7 (2022-06-08)

No significant changes.

## Release v0.12.6 (2022-06-08)

### Bug Fixes

- Fix a crash issue when `dependencies` field is missing from the project metadata. [#92](https://github.com/frostming/pdm-pep517/issues/92)
- Leave `License` and `Summary` fields out from the generated core metadata if they are not given. [#93](https://github.com/frostming/pdm-pep517/issues/93)

## Release v0.12.5 (2022-05-16)

### Features & Improvements

- Allow overriding SCM version with env var. This is useful to build from a source tree without SCM. [#89](https://github.com/frostming/pdm-pep517/issues/89)

## Release v0.12.4 (2022-05-02)

### Bug Fixes

- Fallback the README content type to text/plain if no suffix is given. [#85](https://github.com/frostming/pdm-pep517/issues/85)
- Write license files when preparing metadata for wheels. [#86](https://github.com/frostming/pdm-pep517/issues/86)

## Release v0.12.3 (2022-04-01)

### Bug Fixes

- Do not emit deprecation warnings for `license` field until PEP 639 is accepted.

## Release v0.12.2 (2022-04-01)

### Features & Improvements

- Warn about `editable` not being available for PEP 420 namespace packages. [#79](https://github.com/frostming/pdm-pep517/issues/79)

### Bug Fixes

- Construct RECORD file using `csv.writer` to ensure correct quoting on path for each entry. [#80](https://github.com/frostming/pdm-pep517/issues/80)

## Release v0.12.1 (2022-03-10)

### Bug Fixes

- Don't validate license text for PEP 621 `license` field for now. [#78](https://github.com/frostming/pdm-pep517/issues/78)

## Release v0.12.0 (2022-03-08)

### Features & Improvements

- Implement PEP 639: Improving License Clarity in Project Metadata [#76](https://github.com/frostming/pdm-pep517/issues/76)

### Removals and Deprecations

- Mandates the PEP 621 metadata and raise an error if invalid. [#76](https://github.com/frostming/pdm-pep517/issues/76)

## Release v0.11.2 (2022-02-11)

### Bug Fixes

- Change the default `editable-backend` to `path` until `editables` backend is stable.

## Release v0.11.1 (2022-02-11)

### Bug Fixes

- Fix a bug that version can't be parsed if it is followed by a comment. [#75](https://github.com/frostming/pdm-pep517/issues/75)

## Release v0.11.0 (2022-02-09)

### Features & Improvements

- Drop the support for Python < 3.7. [#72](https://github.com/frostming/pdm-pep517/issues/72)
- Show meaningful error message when version isn't found in the specified file. [#73](https://github.com/frostming/pdm-pep517/issues/73)

### Dependencies

- Switch from `toml` to `tomli` + `tomli_w`. [#71](https://github.com/frostming/pdm-pep517/issues/71)
- Update vendored dependency `pyparsing` to `3.0.7`. [#74](https://github.com/frostming/pdm-pep517/issues/74)

## Release v0.10.2 (2022-01-28)

### Bug Fixes

- Preserve the file mode when building a wheel, also correct the datetime. [#69](https://github.com/frostming/pdm-pep517/issues/69)

### Miscellany

- Use alternatives to replace the deprecated usage of `distutils`. [#69](https://github.com/frostming/pdm-pep517/issues/69)

## Release v0.10.1 (2022-01-14)

### Bug Fixes

- Fix a bug that the proxy module of `editables` backend shadows the extension module with the same name. [#67](https://github.com/frostming/pdm-pep517/issues/67)

## Release v0.10.0 (2021-12-16)

### Features & Improvements

- Add a tool setting `is-purelib` to override the default behavior of determining whether a package is a pure Python library. [#64](https://github.com/frostming/pdm-pep517/issues/64)

## Release v0.9.4 (2021-12-03)

### Bug Fixes

- Fix a bug that version is not frozen in sdist build. [#63](https://github.com/frostming/pdm-pep517/issues/63)

## Release v0.9.3 (2021-12-01)

### Bug Fixes

- Fix a bug that extra dependencies(such as `editables`) are not written in `prepare_metadata_for_build_editable` hook. [#62](https://github.com/frostming/pdm-pep517/issues/62)

## Release v0.9.2 (2021-11-22)

No significant changes.

## Release v0.9.1 (2021-11-22)

No significant changes.

## Release v0.9.0 (2021-11-22)

### Features & Improvements

- To be compliant with PEP 621, `version` is not allowed in the `[project]` table when it is dynamic. Warning users against that usage and suggest to move to the `[tool.pdm]` table. `classifiers` field no longer supports dynamic filling. [#53](https://github.com/frostming/pdm-pep517/issues/53)

## Release v0.8.6 (2021-10-26)

### Bug Fixes

- Fix the editable wheel building to exclude files inside a package. [#45](https://github.com/frostming/pdm-pep517/issues/45)

### Dependencies

- Update vendors:
  - Update `packaging` from `20.4` to `21.0`.
  - Update `cerberus` from `1.3.2` to `1.3.4`. [#52](https://github.com/frostming/pdm-pep517/issues/52)

## Release v0.8.5 (2021-10-07)

### Bug Fixes

- Fix the editable wheel building to exclude files inside a package. [#45](https://github.com/frostming/pdm-pep517/issues/45)

### Dependencies

- Update vendors:
  - Update `packaging` from `20.4` to `21.0`.
  - Update `cerberus` from `1.3.2` to `1.3.4`. [#52](https://github.com/frostming/pdm-pep517/issues/52)

## Release v0.8.4 (2021-09-14)

No significant changes.

## Release v0.8.3 (2021-08-21)

### Features & Improvements

- Allow changing the backend used to generate editable wheels. Currently two are supported: editables(default) and path. [#43](https://github.com/frostming/pdm-pep517/issues/43)

## Release v0.8.1 (2021-08-20)

### Features & Improvements

- Provide a compatibility layer for setuptools to support PEP 660. The backend is exposed as `pdm.pep517.setuptools`. [#41](https://github.com/frostming/pdm-pep517/issues/41)

### Bug Fixes

- Convert "\*" to empty string for `requires-python` metadata. [#40](https://github.com/frostming/pdm-pep517/issues/40)

## Release v0.8.0 (2021-06-29)

### Features & Improvements

- Add new hooks for building editable, which implements [PEP 660](https://www.python.org/dev/peps/pep-0660/). [#33](https://github.com/frostming/pdm-pep517/issues/33)

### Bug Fixes

- Retrieve all Python versions from python.org for classifiers generation. [#29](https://github.com/frostming/pdm-pep517/issues/29)

## Release v0.7.4 (2021-05-10)

### Bug Fixes

- Fix pure Py27 package build wheel failure. [#28](https://github.com/frostming/pdm-pep517/issues/28)

## Release v0.7.3 (2021-05-07)

### Features & Improvements

- Support recursive glob pattern `**` in `includes`, `excludes` and `source-includes`. [#20](https://github.com/frostming/pdm-pep517/issues/20)
- Support passing `config_settings` to the backend APIs. [#23](https://github.com/frostming/pdm-pep517/issues/23)

### Miscellany

- Rewrite the `_merge_globs` function to be clearer and more robust. [#25](https://github.com/frostming/pdm-pep517/issues/25)
- Add type hints to the codebase. [#27](https://github.com/frostming/pdm-pep517/issues/27)

## Release v0.7.2 (2021-04-27)

### Bug Fixes

- Fix files finding error if the glob result of excludes containing directory. [#17](https://github.com/frostming/pdm-pep517/issues/17)

### Dependencies

- Update `toml` from `0.10.1` to `0.10.2`. [#19](https://github.com/frostming/pdm-pep517/issues/19)

## Release v0.7.1 (2021-04-20)

### Bug Fixes

- Fix the pyproject.toml file in sdist builds.

## Release v0.7.0 (2021-04-13)

### Features & Improvements

- Support sdist-only include files list. Include `tests` folder for sdist build if none is given. [#16](https://github.com/frostming/pdm-pep517/issues/16)
- Exclude the files specified by `source-includes` in non-sdist builds. [#16](https://github.com/frostming/pdm-pep517/issues/16)

## Release v0.6.1 (2021-03-29)

### Features & Improvements

- Temporily disable the strict validation.

## Release v0.6.0 (2021-03-29)

### Features & Improvements

- Move the fields that are not specified by PEP 621 to `[tool.pdm]` table. [#14](https://github.com/frostming/pdm-pep517/issues/14)
- Validate PEP 621 metadata. [#15](https://github.com/frostming/pdm-pep517/issues/15)

## Release v0.5.10 (2021-03-24)

### Dependencies

- Remove the external dependency of `importlib-metadata`. [#13](https://github.com/frostming/pdm-pep517/issues/13)

## Release v0.5.9 (2021-03-24)

### Bug Fixes

- Fix a parsing error on reStructuredText description due to missing indentation for empty lines. [#11](https://github.com/frostming/pdm-pep517/issues/11)
- Fix the WHEEL writer to report the correct wheel generator. [#12](https://github.com/frostming/pdm-pep517/issues/12)

## Release v0.5.8 (2021-03-16)

### Bug Fixes

- Fix a bug that platform-specific tags cannot be generated correctly.

## Release v0.5.7 (2021-03-05)

### Bug Fixes

- Fix a bug that python modules under `src` directory without a parent package are not included in the built results nor `py_modules` key in `setup.py`. [#9](https://github.com/frostming/pdm-pep517/issues/9)

## Release v0.5.6 (2021-02-08)

### Bug Fixes

- Don't include redundant `Homepage` in the core metadata.

## Release v0.5.5 (2021-02-05)

### Bug Fixes

- Rewrite the import statements in vendored packages to avoid namespace conflicts.

## Release v0.5.4 (2021-01-26)

### Bug Fixes

- Automatically exclude `tests` directory from the build results when not specified.

## Release v0.5.3 (2021-01-26)

### Bug Fixes

- Fix a bug that default settings include many misc directories that are not Python packages.

## Release v0.5.2 (2021-01-24)

### Bug Fixes

- Fix a bug that `__pypackages__` gets included in the build files unexpectedly.

## Release v0.5.0 (2021-01-11)

### Features & Improvements

- Support PEP 420 implicit namespace packages [#7](https://github.com/frostming/pdm-pep517/issues/7)

## Release v0.4.0 (2020-12-24)

### Features & Improvements

- Autogen trove classifiers based on `requires-python` and `license`. [#6](https://github.com/frostming/pdm-pep517/issues/6)

## Release v0.3.3 (2020-12-22)

### Features & Improvements

- Auto convert legacy metadata format for backward compatibility. [#5](https://github.com/frostming/pdm-pep517/issues/5)

## Release v0.3.2 (2020-12-21)

### Bug Fixes

- Fix setup.py encoding issue. [#4](https://github.com/frostming/pdm-pep517/issues/4)

## Release v0.3.0 (2020-12-21)

### Features & Improvements

- Support [PEP 621](https://www.python.org/dev/peps/pep-0621/) project metadata specification. [#4](https://github.com/frostming/pdm-pep517/issues/4)
