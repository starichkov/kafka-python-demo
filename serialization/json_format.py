import json
from typing import Any

"""JSON and plain-text serialization utilities.

This module contains the concrete serializer and deserializer functions for
JSON and plain-text payloads. They are wired into the public registries
exposed by :mod:`serialization`.
"""


def json_serializer(value: Any) -> bytes:
    """Serialize a Python object to JSON encoded as UTF-8 bytes."""

    return json.dumps(value).encode("utf-8")


def json_deserializer(value: bytes) -> Any:
    """Deserialize UTF-8 JSON bytes into a Python object."""

    text = value.decode("utf-8")
    return json.loads(text)


def plain_text_deserializer(value: bytes) -> str:
    """Decode bytes as UTF-8 text, replacing invalid sequences."""

    return value.decode("utf-8", errors="replace")


def json_or_text_deserializer(value: bytes) -> Any:
    """Try to deserialize JSON, falling back to plain text on failure.

    This mirrors the previous ``try_parse_json`` behavior in ``consumer.py``:
    it first attempts JSON decoding and, if that fails due to invalid JSON or
    invalid UTF-8, it returns a plain-text representation instead.
    """

    try:
        return json_deserializer(value)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return plain_text_deserializer(value)
