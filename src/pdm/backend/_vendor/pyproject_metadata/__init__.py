# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import dataclasses
import email.message
import email.policy
import email.utils
import os
import os.path
import pathlib
import re
import sys
import typing
import warnings


if typing.TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Mapping
    from typing import Any

    from pdm.backend._vendor.packaging.requirements import Requirement

    if sys.version_info < (3, 11):
        from typing_extensions import Self
    else:
        from typing import Self

import pdm.backend._vendor.packaging.markers as pkg_markers
import pdm.backend._vendor.packaging.requirements as pkg_requirements
import pdm.backend._vendor.packaging.specifiers as pkg_specifiers
import pdm.backend._vendor.packaging.utils as pkg_utils
import pdm.backend._vendor.packaging.version as pkg_version


__version__ = '0.9.0b3'

KNOWN_METADATA_VERSIONS = {'2.1', '2.2', '2.3', '2.4'}
PRE_SPDX_METADATA_VERSIONS = {'2.1', '2.2', '2.3'}

KNOWN_TOPLEVEL_FIELDS = {'build-system', 'project', 'tool'}
KNOWN_BUILD_SYSTEM_FIELDS = {'backend-path', 'build-backend', 'requires'}
KNOWN_PROJECT_FIELDS = {
    'authors',
    'classifiers',
    'dependencies',
    'description',
    'dynamic',
    'entry-points',
    'gui-scripts',
    'keywords',
    'license',
    'license-files',
    'maintainers',
    'name',
    'optional-dependencies',
    'readme',
    'requires-python',
    'scripts',
    'urls',
    'version',
}


__all__ = [
    'ConfigurationError',
    'ConfigurationWarning',
    'License',
    'RFC822Message',
    'RFC822Policy',
    'Readme',
    'StandardMetadata',
    'validate_build_system',
    'validate_project',
    'validate_top_level',
]


def __dir__() -> list[str]:
    return __all__


def validate_top_level(pyproject: Mapping[str, Any]) -> None:
    extra_keys = set(pyproject) - KNOWN_TOPLEVEL_FIELDS
    if extra_keys:
        msg = f'Extra keys present in pyproject.toml: {extra_keys}'
        raise ConfigurationError(msg)


def validate_build_system(pyproject: Mapping[str, Any]) -> None:
    extra_keys = set(pyproject.get('build-system', [])) - KNOWN_BUILD_SYSTEM_FIELDS
    if extra_keys:
        msg = f'Extra keys present in "build-system": {extra_keys}'
        raise ConfigurationError(msg)


def validate_project(pyproject: Mapping[str, Any]) -> None:
    extra_keys = set(pyproject.get('project', [])) - KNOWN_PROJECT_FIELDS
    if extra_keys:
        msg = f'Extra keys present in "project": {extra_keys}'
        raise ConfigurationError(msg)


class ConfigurationError(Exception):
    """Error in the backend metadata."""

    def __init__(self, msg: str, *, key: str | None = None):
        super().__init__(msg)
        self._key = key

    @property
    def key(self) -> str | None:  # pragma: no cover
        return self._key


class ConfigurationWarning(UserWarning):
    """Warnings about backend metadata."""


@dataclasses.dataclass
class _SmartMessageSetter:
    """
    This provides a nice internal API for setting values in an Message to
    reduce boilerplate.

    If a value is None, do nothing.
    If a value contains a newline, indent it (may produce a warning in the future).
    """

    message: email.message.Message

    def __setitem__(self, name: str, value: str | None) -> None:
        if not value:
            return
        self.message[name] = value


class RFC822Policy(email.policy.EmailPolicy):
    """
    This is `email.policy.EmailPolicy`, but with a simple ``header_store_parse``
    implementation that handles multiline values, and some nice defaults.
    """

    utf8 = True
    mangle_from_ = False
    max_line_length = 0

    def header_store_parse(self, name: str, value: str) -> tuple[str, str]:
        size = len(name) + 2
        value = value.replace('\n', '\n' + ' ' * size)
        return (name, value)


class RFC822Message(email.message.EmailMessage):
    """
    This is `email.message.EmailMessage` with two small changes: it defaults to
    our `RFC822Policy`, and it correctly writes unicode when being called
    with `bytes()`.
    """

    def __init__(self) -> None:
        super().__init__(policy=RFC822Policy())

    def as_bytes(
        self, unixfrom: bool = False, policy: email.policy.Policy | None = None
    ) -> bytes:
        return self.as_string(unixfrom, policy=policy).encode('utf-8')


class DataFetcher:
    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = data

    def __contains__(self, key: str) -> bool:
        val = self._data
        try:
            for part in key.split('.'):
                val = val[part]
        except KeyError:
            return False
        return True

    def get(self, key: str) -> Any:
        val = self._data
        for part in key.split('.'):
            val = val[part]
        return val

    def get_str(self, key: str) -> str | None:
        try:
            val = self.get(key)
            if not isinstance(val, str):
                msg = f'Field "{key}" has an invalid type, expecting a string (got "{val}")'
                raise ConfigurationError(msg, key=key)
            return val
        except KeyError:
            return None

    def get_list(self, key: str) -> list[str] | None:
        try:
            val = self.get(key)
            if not isinstance(val, list):
                msg = f'Field "{key}" has an invalid type, expecting a list of strings (got "{val}")'
                raise ConfigurationError(msg, key=val)
            for item in val:
                if not isinstance(item, str):
                    msg = f'Field "{key}" contains item with invalid type, expecting a string (got "{item}")'
                    raise ConfigurationError(msg, key=key)
            return val
        except KeyError:
            return None

    def get_dict(self, key: str) -> dict[str, str]:
        try:
            val = self.get(key)
            if not isinstance(val, dict):
                msg = f'Field "{key}" has an invalid type, expecting a dictionary of strings (got "{val}")'
                raise ConfigurationError(msg, key=key)
            for subkey, item in val.items():
                if not isinstance(item, str):
                    msg = f'Field "{key}.{subkey}" has an invalid type, expecting a string (got "{item}")'
                    raise ConfigurationError(msg, key=f'{key}.{subkey}')
            return val
        except KeyError:
            return {}

    def get_people(self, key: str) -> list[tuple[str, str | None]]:
        try:
            val = self.get(key)
            if not (
                isinstance(val, list)
                and all(isinstance(x, dict) for x in val)
                and all(
                    isinstance(item, str)
                    for items in [_dict.values() for _dict in val]
                    for item in items
                )
            ):
                msg = (
                    f'Field "{key}" has an invalid type, expecting a list of '
                    f'dictionaries containing the "name" and/or "email" keys (got "{val}")'
                )
                raise ConfigurationError(msg, key=key)
            return [(entry.get('name', 'Unknown'), entry.get('email')) for entry in val]
        except KeyError:
            return []


class ProjectFetcher(DataFetcher):
    def get_license(self, project_dir: pathlib.Path) -> License | str | None:
        if 'project.license' not in self:
            return None

        val = self.get('project.license')
        if isinstance(val, str):
            return self.get_str('project.license')

        if isinstance(val, dict):
            _license = self.get_dict('project.license')
        else:
            msg = f'Field "project.license" has an invalid type, expecting a string or dictionary of strings (got "{val}")'
            raise ConfigurationError(msg)

        for field in _license:
            if field not in ('file', 'text'):
                msg = f'Unexpected field "project.license.{field}"'
                raise ConfigurationError(msg, key=f'project.license.{field}')

        file: pathlib.Path | None = None
        filename = self.get_str('project.license.file')
        text = self.get_str('project.license.text')

        if (filename and text) or (not filename and not text):
            msg = f'Invalid "project.license" value, expecting either "file" or "text" (got "{_license}")'
            raise ConfigurationError(msg, key='project.license')

        if filename:
            file = project_dir.joinpath(filename)
            if not file.is_file():
                msg = f'License file not found ("{filename}")'
                raise ConfigurationError(msg, key='project.license.file')
            text = file.read_text(encoding='utf-8')

        assert text is not None
        return License(text, file)

    def get_license_files(self, project_dir: pathlib.Path) -> list[pathlib.Path] | None:
        license_files = self.get_list('project.license-files')
        if license_files is None:
            return None

        return list(_get_files_from_globs(project_dir, license_files))

    def get_readme(self, project_dir: pathlib.Path) -> Readme | None:  # noqa: C901
        if 'project.readme' not in self:
            return None

        filename: str | None
        file: pathlib.Path | None = None
        text: str | None
        content_type: str | None

        readme = self.get('project.readme')
        if isinstance(readme, str):
            # readme is a file
            text = None
            filename = readme
            if filename.endswith('.md'):
                content_type = 'text/markdown'
            elif filename.endswith('.rst'):
                content_type = 'text/x-rst'
            else:
                msg = f'Could not infer content type for readme file "{filename}"'
                raise ConfigurationError(msg, key='project.readme')
        elif isinstance(readme, dict):
            # readme is a dict containing either 'file' or 'text', and content-type
            for field in readme:
                if field not in ('content-type', 'file', 'text'):
                    msg = f'Unexpected field "project.readme.{field}"'
                    raise ConfigurationError(msg, key=f'project.readme.{field}')
            content_type = self.get_str('project.readme.content-type')
            filename = self.get_str('project.readme.file')
            text = self.get_str('project.readme.text')
            if (filename and text) or (not filename and not text):
                msg = f'Invalid "project.readme" value, expecting either "file" or "text" (got "{readme}")'
                raise ConfigurationError(msg, key='project.readme')
            if not content_type:
                msg = 'Field "project.readme.content-type" missing'
                raise ConfigurationError(msg, key='project.readme.content-type')
        else:
            msg = (
                f'Field "project.readme" has an invalid type, expecting either, '
                f'a string or dictionary of strings (got "{readme}")'
            )
            raise ConfigurationError(msg, key='project.readme')

        if filename:
            file = project_dir.joinpath(filename)
            if not file.is_file():
                msg = f'Readme file not found ("{filename}")'
                raise ConfigurationError(msg, key='project.readme.file')
            text = file.read_text(encoding='utf-8')

        assert text is not None
        return Readme(text, file, content_type)

    def get_dependencies(self) -> list[Requirement]:
        requirement_strings = self.get_list('project.dependencies') or []

        requirements: list[Requirement] = []
        for req in requirement_strings:
            try:
                requirements.append(pkg_requirements.Requirement(req))
            except pkg_requirements.InvalidRequirement as e:
                msg = (
                    'Field "project.dependencies" contains an invalid PEP 508 '
                    f'requirement string "{req}" ("{e}")'
                )
                raise ConfigurationError(msg) from None
        return requirements

    def get_optional_dependencies(
        self,
    ) -> dict[str, list[Requirement]]:
        try:
            val = self.get('project.optional-dependencies')
        except KeyError:
            return {}

        requirements_dict: dict[str, list[Requirement]] = {}
        if not isinstance(val, dict):
            msg = (
                'Field "project.optional-dependencies" has an invalid type, expecting a '
                f'dictionary of PEP 508 requirement strings (got "{val}")'
            )
            raise ConfigurationError(msg)
        for extra, requirements in val.copy().items():
            assert isinstance(extra, str)
            if not isinstance(requirements, list):
                msg = (
                    f'Field "project.optional-dependencies.{extra}" has an invalid type, expecting a '
                    f'dictionary PEP 508 requirement strings (got "{requirements}")'
                )
                raise ConfigurationError(msg)
            requirements_dict[extra] = []
            for req in requirements:
                if not isinstance(req, str):
                    msg = (
                        f'Field "project.optional-dependencies.{extra}" has an invalid type, '
                        f'expecting a PEP 508 requirement string (got "{req}")'
                    )
                    raise ConfigurationError(msg)
                try:
                    requirements_dict[extra].append(
                        pkg_requirements.Requirement(req)
                    )
                except pkg_requirements.InvalidRequirement as e:
                    msg = (
                        f'Field "project.optional-dependencies.{extra}" contains '
                        f'an invalid PEP 508 requirement string "{req}" ("{e}")'
                    )
                    raise ConfigurationError(msg) from None
        return dict(requirements_dict)

    def get_entrypoints(self) -> dict[str, dict[str, str]]:
        try:
            val = self.get('project.entry-points')
        except KeyError:
            return {}
        if not isinstance(val, dict):
            msg = (
                'Field "project.entry-points" has an invalid type, expecting a '
                f'dictionary of entrypoint sections (got "{val}")'
            )
            raise ConfigurationError(msg)
        for section, entrypoints in val.items():
            assert isinstance(section, str)
            if not re.match(r'^\w+(\.\w+)*$', section):
                msg = (
                    'Field "project.entry-points" has an invalid value, expecting a name '
                    f'containing only alphanumeric, underscore, or dot characters (got "{section}")'
                )
                raise ConfigurationError(msg)
            if not isinstance(entrypoints, dict):
                msg = (
                    f'Field "project.entry-points.{section}" has an invalid type, expecting a '
                    f'dictionary of entrypoints (got "{entrypoints}")'
                )
                raise ConfigurationError(msg)
            for name, entrypoint in entrypoints.items():
                assert isinstance(name, str)
                if not isinstance(entrypoint, str):
                    msg = (
                        f'Field "project.entry-points.{section}.{name}" has an invalid type, '
                        f'expecting a string (got "{entrypoint}")'
                    )
                    raise ConfigurationError(msg)
        return val


class License(typing.NamedTuple):
    text: str
    file: pathlib.Path | None


class Readme(typing.NamedTuple):
    text: str
    file: pathlib.Path | None
    content_type: str


@dataclasses.dataclass
class StandardMetadata:
    name: str
    version: pkg_version.Version | None = None
    description: str | None = None
    license: License | str | None = None
    license_files: list[pathlib.Path] | None = None
    readme: Readme | None = None
    requires_python: pkg_specifiers.SpecifierSet | None = None
    dependencies: list[Requirement] = dataclasses.field(default_factory=list)
    optional_dependencies: dict[str, list[Requirement]] = dataclasses.field(
        default_factory=dict
    )
    entrypoints: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    authors: list[tuple[str, str | None]] = dataclasses.field(default_factory=list)
    maintainers: list[tuple[str, str | None]] = dataclasses.field(default_factory=list)
    urls: dict[str, str] = dataclasses.field(default_factory=dict)
    classifiers: list[str] = dataclasses.field(default_factory=list)
    keywords: list[str] = dataclasses.field(default_factory=list)
    scripts: dict[str, str] = dataclasses.field(default_factory=dict)
    gui_scripts: dict[str, str] = dataclasses.field(default_factory=dict)
    dynamic: list[str] = dataclasses.field(default_factory=list)

    _metadata_version: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self, *, warn: bool = True) -> None:
        if (
            self._metadata_version
            and self._metadata_version not in KNOWN_METADATA_VERSIONS
        ):
            msg = f'The metadata_version must be one of {KNOWN_METADATA_VERSIONS} or None (default)'
            raise ConfigurationError(msg)

        # See https://packaging.python.org/en/latest/specifications/core-metadata/#name and
        # https://packaging.python.org/en/latest/specifications/name-normalization/#name-format
        if not re.match(
            r'^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$', self.name, re.IGNORECASE
        ):
            msg = (
                f'Invalid project name "{self.name}". A valid name consists only of ASCII letters and '
                'numbers, period, underscore and hyphen. It must start and end with a letter or number'
            )
            raise ConfigurationError(msg)

        if self.license_files is not None and isinstance(self.license, License):
            msg = '"project.license-files" must not be used when "project.license" is not a SPDX license expression'
            raise ConfigurationError(msg)

        if isinstance(self.license, str) and any(
            c.startswith('License ::') for c in self.classifiers
        ):
            msg = 'Setting "project.license" to an SPDX license expression is not compatible with "License ::" classifiers'
            raise ConfigurationError(msg)

        if warn and self.metadata_version not in PRE_SPDX_METADATA_VERSIONS:
            if isinstance(self.license, License):
                warnings.warn(
                    'Set "project.license" to an SPDX license expression for metadata >= 2.4',
                    ConfigurationWarning,
                    stacklevel=2,
                )
            elif any(c.startswith('License ::') for c in self.classifiers):
                warnings.warn(
                    '"License ::" classifiers are deprecated for metadata >= 2.4, use a SPDX license expression for "project.license" instead',
                    ConfigurationWarning,
                    stacklevel=2,
                )

        if (
            isinstance(self.license, str)
            and self._metadata_version in PRE_SPDX_METADATA_VERSIONS
        ):
            msg = 'Setting "project.license" to an SPDX license expression is supported only when emitting metadata version >= 2.4'
            raise ConfigurationError(msg)

        if (
            self.license_files is not None
            and self._metadata_version in PRE_SPDX_METADATA_VERSIONS
        ):
            msg = '"project.license-files" is supported only when emitting metadata version >= 2.4'
            raise ConfigurationError(msg)

    @property
    def metadata_version(self) -> str:
        if self._metadata_version is None:
            if isinstance(self.license, str) or self.license_files is not None:
                return '2.4'
            if self.dynamic:
                return '2.2'
            return '2.1'
        return self._metadata_version

    @property
    def canonical_name(self) -> str:
        return pkg_utils.canonicalize_name(self.name)

    @classmethod
    def from_pyproject(
        cls,
        data: Mapping[str, Any],
        project_dir: str | os.PathLike[str] = os.path.curdir,
        metadata_version: str | None = None,
        *,
        allow_extra_keys: bool | None = None,
    ) -> Self:
        fetcher = ProjectFetcher(data)
        project_dir = pathlib.Path(project_dir)

        if 'project' not in fetcher:
            msg = 'Section "project" missing in pyproject.toml'
            raise ConfigurationError(msg)

        if allow_extra_keys is None:
            try:
                validate_project(data)
            except ConfigurationError as err:
                warnings.warn(str(err), ConfigurationWarning, stacklevel=2)
        elif not allow_extra_keys:
            validate_project(data)

        dynamic = fetcher.get_list('project.dynamic') or []
        if 'name' in dynamic:
            msg = 'Unsupported field "name" in "project.dynamic"'
            raise ConfigurationError(msg)

        for field in dynamic:
            if field in data['project']:
                msg = f'Field "project.{field}" declared as dynamic in "project.dynamic" but is defined'
                raise ConfigurationError(msg)

        name = fetcher.get_str('project.name')
        if not name:
            msg = 'Field "project.name" missing'
            raise ConfigurationError(msg)

        version_string = fetcher.get_str('project.version')
        requires_python_string = fetcher.get_str('project.requires-python')
        version = pkg_version.Version(version_string) if version_string else None

        if version is None and 'version' not in dynamic:
            msg = 'Field "project.version" missing and "version" not specified in "project.dynamic"'
            raise ConfigurationError(msg)

        # Description fills Summary, which cannot be multiline
        # However, throwing an error isn't backward compatible,
        # so leave it up to the users for now.
        description = fetcher.get_str('project.description')

        return cls(
            name,
            version,
            description,
            fetcher.get_license(project_dir),
            fetcher.get_license_files(project_dir),
            fetcher.get_readme(project_dir),
            pkg_specifiers.SpecifierSet(requires_python_string)
            if requires_python_string
            else None,
            fetcher.get_dependencies(),
            fetcher.get_optional_dependencies(),
            fetcher.get_entrypoints(),
            fetcher.get_people('project.authors'),
            fetcher.get_people('project.maintainers'),
            fetcher.get_dict('project.urls'),
            fetcher.get_list('project.classifiers') or [],
            fetcher.get_list('project.keywords') or [],
            fetcher.get_dict('project.scripts'),
            fetcher.get_dict('project.gui-scripts'),
            dynamic,
            metadata_version,
        )

    def _update_dynamic(self, value: Any) -> None:
        if value and 'version' in self.dynamic:
            self.dynamic.remove('version')

    def __setattr__(self, name: str, value: Any) -> None:
        # update dynamic when version is set
        if name == 'version' and hasattr(self, 'dynamic'):
            self._update_dynamic(value)
        super().__setattr__(name, value)

    def as_rfc822(self) -> RFC822Message:
        message = RFC822Message()
        self.write_to_rfc822(message)
        return message

    def write_to_rfc822(self, message: email.message.Message) -> None:  # noqa: C901
        self.validate(warn=False)

        smart_message = _SmartMessageSetter(message)

        smart_message['Metadata-Version'] = self.metadata_version
        smart_message['Name'] = self.name
        if not self.version:
            msg = 'Missing version field'
            raise ConfigurationError(msg)
        smart_message['Version'] = str(self.version)
        # skip 'Platform'
        # skip 'Supported-Platform'
        if self.description:
            smart_message['Summary'] = self.description
        smart_message['Keywords'] = ','.join(self.keywords)
        if 'homepage' in self.urls:
            smart_message['Home-page'] = self.urls['homepage']
        # skip 'Download-URL'
        smart_message['Author'] = self._name_list(self.authors)
        smart_message['Author-Email'] = self._email_list(self.authors)
        smart_message['Maintainer'] = self._name_list(self.maintainers)
        smart_message['Maintainer-Email'] = self._email_list(self.maintainers)

        if isinstance(self.license, License):
            smart_message['License'] = self.license.text
        elif isinstance(self.license, str):
            smart_message['License-Expression'] = self.license

        if self.license_files is not None:
            for license_file in sorted(set(self.license_files)):
                smart_message['License-File'] = os.fspath(license_file.as_posix())

        for classifier in self.classifiers:
            smart_message['Classifier'] = classifier
        # skip 'Provides-Dist'
        # skip 'Obsoletes-Dist'
        # skip 'Requires-External'
        for name, url in self.urls.items():
            smart_message['Project-URL'] = f'{name.capitalize()}, {url}'
        if self.requires_python:
            smart_message['Requires-Python'] = str(self.requires_python)
        for dep in self.dependencies:
            smart_message['Requires-Dist'] = str(dep)
        for extra, requirements in self.optional_dependencies.items():
            norm_extra = extra.replace('.', '-').replace('_', '-').lower()
            smart_message['Provides-Extra'] = norm_extra
            for requirement in requirements:
                smart_message['Requires-Dist'] = str(
                    self._build_extra_req(norm_extra, requirement)
                )
        if self.readme:
            if self.readme.content_type:
                smart_message['Description-Content-Type'] = self.readme.content_type
            message.set_payload(self.readme.text)
        # Core Metadata 2.2
        if self.metadata_version != '2.1':
            for field in self.dynamic:
                if field in ('name', 'version'):
                    msg = f'Field cannot be dynamic: {field}'
                    raise ConfigurationError(msg)
                smart_message['Dynamic'] = field

    def _name_list(self, people: list[tuple[str, str | None]]) -> str:
        return ', '.join(name for name, email_ in people if not email_)

    def _email_list(self, people: list[tuple[str, str | None]]) -> str:
        return ', '.join(
            email.utils.formataddr((name, _email)) for name, _email in people if _email
        )

    def _build_extra_req(
        self,
        extra: str,
        requirement: Requirement,
    ) -> Requirement:
        # append or add our extra marker
        requirement = copy.copy(requirement)
        if requirement.marker:
            if 'or' in requirement.marker._markers:
                requirement.marker = pkg_markers.Marker(
                    f'({requirement.marker}) and extra == "{extra}"'
                )
            else:
                requirement.marker = pkg_markers.Marker(
                    f'{requirement.marker} and extra == "{extra}"'
                )
        else:
            requirement.marker = pkg_markers.Marker(f'extra == "{extra}"')
        return requirement


def _get_files_from_globs(
    project_dir: pathlib.Path, globs: Iterable[str]
) -> Generator[pathlib.Path, None, None]:
    for glob in globs:
        if glob.startswith(('..', '/')):
            msg = f'"{glob}" is an invalid "project.license-files" glob: the pattern must match files within the project directory'
            raise ConfigurationError(msg)
        files = [f for f in project_dir.glob(glob) if f.is_file()]
        if not files:
            msg = f'Every pattern in "project.license-files" must match at least one file: "{glob}" did not match any'
            raise ConfigurationError(msg)
        for f in files:
            yield f.relative_to(project_dir)
