import functools
import re
from typing import Any, Callable, Dict, List, Optional, Union

from pdm.pep517.utils import path_to_url, safe_name

ConvertFunc = Callable[[Any, Dict[str, Any]], Any]
RequirementDict = Union[str, Dict[str, Union[bool, str]]]

UNSET = object()
VCS_SCHEMA = ("git", "hg", "svn", "bzr")


class Requirement:
    """Base class of a package requirement.
    A requirement is a (virtual) specification of a package which contains
    some constraints of version, python version, or other marker.
    The dependency specification follows PEP 440.
    """

    attributes = (
        "allow_prereleases",
        "extras",
        "index",
        "marker",
        "name",
        "path",
        "ref",
        "url",
        "version",
    )

    def __init__(self, **kwargs):
        for key in self.attributes:
            if key in kwargs:
                if key == "version":
                    kwargs[key] = "" if kwargs[key] == "*" else kwargs[key]
                setattr(self, key, kwargs[key])
            else:
                setattr(self, key, None)
        if self.name:
            self.project_name = safe_name(self.name)
            self.key = self.project_name.lower()

    def identify(self) -> Optional[str]:
        """Return the identity of the requirement."""
        if not self.key:
            return None
        extras = "[{}]".format(",".join(sorted(self.extras))) if self.extras else ""
        return self.key + extras

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.as_line()}>"

    def __str__(self) -> str:
        return self.as_line()

    @classmethod
    def from_req_dict(cls, name: str, req_dict: RequirementDict) -> "Requirement":
        """Create a requirement from a PDM dependency entry."""
        # TODO: validate req_dict
        kwargs = {}
        kwargs["name"] = name
        if isinstance(req_dict, str):  # Version specifier only.
            kwargs["version"] = req_dict
        else:
            kwargs.update(req_dict)
        for vcs in VCS_SCHEMA:
            if vcs in kwargs:
                repo = kwargs.pop(vcs)  # type: str
                branch_or_tag = kwargs.pop("branch", kwargs.pop("tag", ""))
                url = cls._build_vcs_url(
                    vcs, repo, kwargs.pop("ref", ""), branch_or_tag
                )
                kwargs.update(url=url, vcs=vcs)
                break
        if "path" in kwargs and "url" not in kwargs:
            kwargs["url"] = path_to_url(kwargs["path"])

        return Requirement(**kwargs)

    def as_line(self) -> str:
        """Serialize the requirement into a PEP 440 format string."""
        extras = f"[{','.join(sorted(self.extras))}]" if self.extras else ""
        marker = f"; {self.marker}" if self.marker else ""
        mid = f" @ {self.url}" if self.url else ""
        return f"{self.project_name}{extras}{self.version or ''}{mid}{marker}"

    @staticmethod
    def _build_vcs_url(
        vcs: str,
        repo: str,
        ref: str = "",
        branch_or_tag: str = "",
    ) -> str:
        ref_part = (
            f"@{branch_or_tag}#{ref}"
            if ref and branch_or_tag
            else ""
            if not ref and not branch_or_tag
            else f"@{branch_or_tag or ref}"
        )
        return f"{vcs}+{repo}{ref_part}"


class Converter:
    def __init__(self) -> None:
        self._key_converters: Dict[str, ConvertFunc] = {}
        self._global_converters: List[ConvertFunc] = []

    def register_converter(
        self, field: Optional[str] = None, new_field: Optional[str] = None
    ) -> Callable[[ConvertFunc], ConvertFunc]:
        def wrapper(func: ConvertFunc) -> ConvertFunc:
            func.field = new_field or func.__name__
            if field is not None:
                self._key_converters[field] = func
            else:
                self._global_converters.append(func)
            return func

        return wrapper

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for k, v in list(data.items()):
            if k in self._key_converters:
                func = self._key_converters[k]
                new_value = func(v, result)
                if new_value is UNSET:
                    continue
                result[func.field] = new_value
                data.pop(k, None)
        for func in self._global_converters:
            new_value = func(data, result)
            if new_value is UNSET:
                continue
            result[func.field] = new_value
        result.update(data)
        return result


converter = Converter()
NAME_EMAIL_RE = re.compile(r"(?P<name>[^,]+?)\s*<(?P<email>.+)>\s*$")


@converter.register_converter("author")
def authors(value, result):
    return [NAME_EMAIL_RE.match(value).groupdict()]


@converter.register_converter("maintainer")
def maintainers(value, result):
    return [NAME_EMAIL_RE.match(value).groupdict()]


@converter.register_converter("version")
def version(value, result):
    if not isinstance(value, str):
        result.setdefault("dynamic", []).append("version")
    return value


@converter.register_converter("python_requires", new_field="requires-python")
def requires_python(value, result):
    return value


@converter.register_converter("license")
def license(value, result):
    return {"text": value}


@converter.register_converter("source")
def source(value, result):
    return UNSET


@converter.register_converter("homepage")
def homepage(value, result):
    result.setdefault("urls", {})["homepage"] = value
    return UNSET


@converter.register_converter("project_urls")
def urls(value, result):
    result.setdefault("urls", {}).update(value)
    return UNSET


@converter.register_converter("dependencies")
def dependencies(value, result):
    return [
        Requirement.from_req_dict(name, req).as_line() for name, req in value.items()
    ]


@converter.register_converter("dev-dependencies", new_field="dev-dependencies")
def dev_dependencies(value, result):
    return [
        Requirement.from_req_dict(name, req).as_line() for name, req in value.items()
    ]


@converter.register_converter(new_field="optional-dependencies")
def optional_dependencies(source, result):
    extras = {}
    for key, reqs in list(source.items()):
        if key.endswith("-dependencies") and key != "dev-dependencies":
            extra_key = key.split("-", 1)[0]
            extras[extra_key] = [
                Requirement.from_req_dict(name, req).as_line()
                for name, req in reqs.items()
            ]
            source.pop(key)
    for name in source.pop("extras", []):
        if name in extras:
            continue
        if "=" in name:
            key, parts = name.split("=", 1)
            parts = parts.split("|")
            extras[key] = list(
                functools.reduce(lambda x, y: x.union(extras[y]), parts, set())
            )
    return extras


@converter.register_converter("cli")
def scripts(value, result):
    return value


@converter.register_converter("entry_points", new_field="entry-points")
def entry_points(value, result):
    return value


@converter.register_converter("scripts")
def run_scripts(value, result):
    return UNSET


@converter.register_converter("allow_prereleases")
def allow_prereleases(value, result):
    return UNSET


def convert_legacy(data: Dict[str, Any]) -> Dict[str, Any]:
    return converter.convert(data)
