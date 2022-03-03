from typing import Mapping

from pdm.pep517._vendor import cerberus
from pdm.pep517.exceptions import PEP621ValidationError

README_RULE = [
    {"type": "string"},
    {
        "type": "dict",
        "schema": {
            "file": {"type": "string", "required": True},
            "content-type": {"type": "string", "required": True},
        },
    },
    {
        "type": "dict",
        "schema": {
            "text": {"type": "string", "required": True},
            "content-type": {"type": "string", "required": True},
        },
    },
]

LICENSE_RULE = [
    {"type": "dict", "schema": {"file": {"type": "string", "required": True}}},
    {"type": "dict", "schema": {"text": {"type": "string", "required": True}}},
]

LICENSE_FILE_RULE = [
    {
        "type": "dict",
        "schema": {"paths": {"type": "list", "schema": {"type": "string"}}},
    },
    {
        "type": "dict",
        "schema": {"globs": {"type": "list", "schema": {"type": "string"}}},
    },
]

AUTHOR_RULE = {
    "type": "list",
    "schema": {
        "type": "dict",
        "schema": {"name": {"type": "string"}, "email": {"type": "string"}},
    },
}


PEP621_SCHEMA = {
    "name": {"type": "string", "required": True},
    "version": {"type": "string"},
    "description": {"type": "string"},
    "readme": {"oneof": README_RULE},
    "requires-python": {"type": "string"},
    "license": {"oneof": LICENSE_RULE},
    "license-expression": {"type": "string"},
    "license-files": {"oneof": LICENSE_FILE_RULE},
    "authors": AUTHOR_RULE,
    "maintainers": AUTHOR_RULE,
    "keywords": {"type": "list", "schema": {"type": "string"}},
    "classifiers": {"type": "list", "schema": {"type": "string"}},
    "urls": {"type": "dict", "valuesrules": {"type": "string"}},
    "scripts": {"type": "dict", "valuesrules": {"type": "string"}},
    "gui-scripts": {"type": "dict", "valuesrules": {"type": "string"}},
    "entry-points": {
        "type": "dict",
        "valuesrules": {"type": "dict", "valuesrules": {"type": "string"}},
    },
    "dependencies": {"type": "list", "schema": {"type": "string"}},
    "optional-dependencies": {
        "type": "dict",
        "valuesrules": {"type": "list", "schema": {"type": "string"}},
    },
    "dynamic": {"type": "list", "schema": {"type": "string"}},
}


def validate_pep621(data: Mapping, raising: bool = False) -> bool:
    """Validate the data against PEP 621 specification.
    If raising is True, raise an error with the validation error information.
    """
    validator = cerberus.Validator(PEP621_SCHEMA)
    result = validator.validate(data)
    if raising and not result:
        raise PEP621ValidationError(validator.errors)
    return result
