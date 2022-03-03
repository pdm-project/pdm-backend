import warnings

from pdm.pep517._vendor.license_expression import (
    LicenseSymbol,
    Licensing,
    get_spdx_licensing,
)
from pdm.pep517.exceptions import MetadataError, PDMWarning


def get_licensing() -> Licensing:
    """Get the spdx licensing with two additional license symbols."""
    extra_identifiers = ["LicenseRef-Public-Domain", "LicenseRef-Proprietary"]
    licensing = get_spdx_licensing()
    for identifier in extra_identifiers:
        symbol = LicenseSymbol(identifier)
        licensing.known_symbols[symbol.key] = symbol
        licensing.known_symbols_lowercase[symbol.key.lower()] = symbol
    return licensing


_licensing = get_licensing()


def normalize_expression(expression: str) -> str:
    """Normalize a SPDX license expression."""
    validate_result = _licensing.validate(expression)
    if validate_result.errors:
        raise MetadataError("license-expression", validate_result.errors)
    result = validate_result.normalized_expression or expression
    if result != expression:
        warnings.warn(
            f"License expression normalized to '{result}'", PDMWarning, stacklevel=2
        )
    return result
