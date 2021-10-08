"""
    Extensible validation for Python dictionaries.

    :copyright: 2012-2021 by Nicola Iarocci.
    :license: ISC, see LICENSE for more details.

    Full documentation is available at https://python-cerberus.org/

"""

from __future__ import absolute_import

from pdm.pep517._vendor.cerberus.validator import DocumentError, Validator
from pdm.pep517._vendor.cerberus.schema import rules_set_registry, schema_registry, SchemaError
from pdm.pep517._vendor.cerberus.utils import TypeDefinition


__version__ = "unknown"

__all__ = [
    DocumentError.__name__,
    SchemaError.__name__,
    TypeDefinition.__name__,
    Validator.__name__,
    "schema_registry",
    "rules_set_registry",
]
