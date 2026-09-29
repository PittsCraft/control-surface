"""Strict JSON reading, shared by the journal codec and the settings reader.

Python's parser accepts duplicate keys (the last one wins) and the constants `NaN` and `Infinity`.
Both are refused here: a file the chain reads must mean one thing.
"""

import json
from typing import NoReturn, cast


class JsonError(ValueError):
    pass


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            message = f"duplicate key {key!r}"
            raise JsonError(message)
        result[key] = value
    return result


def _constant(name: str) -> NoReturn:
    message = f"{name} is not valid JSON"
    raise JsonError(message)


def loads_object(text: str) -> dict[str, object]:
    """Parse a JSON text that must be one object."""
    try:
        value: object = json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    except json.JSONDecodeError as error:
        message = f"not valid JSON: {error.msg} (column {error.colno})"
        raise JsonError(message) from error
    except (ValueError, RecursionError) as error:  # oversized integer, nesting too deep
        message = f"not valid JSON: {error}"
        raise JsonError(message) from error
    if not isinstance(value, dict):
        message = "expected a JSON object"
        raise JsonError(message)
    return cast("dict[str, object]", value)
