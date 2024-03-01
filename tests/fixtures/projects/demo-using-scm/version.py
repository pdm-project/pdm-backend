from pdm.backend.hooks.version import SCMVersion


def format_version(version: SCMVersion) -> str:
    return f"{version.version}rc{version.distance or 0}"
