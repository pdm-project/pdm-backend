from typing import Mapping

from pdm.pep517._vendor import cerberus

VERSION_RULE = [
    {"type": "string"},
    {
        "type": "dict",
        "schema": {"from": {"type": "string"}, "use_scm": {"type": "boolean"}},
    },
]

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

AUTHOR_RULE = {
    "type": "list",
    "schema": {
        "type": "dict",
        "schema": {"name": {"type": "string"}, "email": {"type": "string"}},
    },
}


PEP621_SCHEMA = {
    "name": {"type": "string", "required": True},
    "version": {"anyof": VERSION_RULE},
    "description": {"type": "string"},
    "readme": {"oneof": README_RULE},
    "requires-python": {"type": "string"},
    "license": {"oneof": LICENSE_RULE},
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


class PEP621ValidationError(ValueError):
    def __init__(self, errors):
        super().__init__(errors)
        self.errors = errors


def validate_pep621(data: Mapping, raising: bool = False) -> bool:
    """Validate the data against PEP 621 specification.
    If raising is True, raise an error with the validation error information.
    """
    validator = cerberus.Validator(PEP621_SCHEMA)
    result = validator.validate(data)
    if raising and not result:
        raise PEP621ValidationError(validator.errors)
    return result
