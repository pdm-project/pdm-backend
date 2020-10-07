from typing import Dict, Optional, Union

from .utils import path_to_url, safe_name

VCS_SCHEMA = ("git", "hg", "svn", "bzr")
RequirementDict = Union[str, Dict[str, Union[bool, str]]]


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
