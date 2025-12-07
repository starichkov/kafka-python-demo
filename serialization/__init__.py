from typing import Any, Callable, Dict, Optional

"""Serialization package for Kafka messages.

This package provides pluggable serializers and deserializers that can be
reused by both the producer and the consumer.

Current built-in formats:

* ``json`` – serialize Python objects as JSON encoded in UTF-8 bytes.
* ``plain_text`` – decode bytes as UTF-8 text with replacement for errors.
* ``json_or_text`` – try to decode JSON first, fall back to plain text.

The registries ``SERIALIZERS`` and ``DESERIALIZERS`` expose these
implementations under string keys so additional formats can be plugged in
later without changing producer/consumer code.
"""

Serializer = Callable[[Any], bytes]
Deserializer = Callable[[bytes], Any]

from .json_format import (
    json_serializer,
    json_deserializer,
    plain_text_deserializer,
    json_or_text_deserializer,
)

try:
    # Protobuf support is optional and only used when requested
    from .protobuf_format import protobuf_serializer, protobuf_deserializer
    _PROTOBUF_AVAILABLE = True
except Exception:  # pragma: no cover - exercised in envs without protobuf
    protobuf_serializer = None  # type: ignore
    protobuf_deserializer = None  # type: ignore
    _PROTOBUF_AVAILABLE = False

SERIALIZERS: Dict[str, Serializer] = {
    "json": json_serializer,
}

if _PROTOBUF_AVAILABLE:
    SERIALIZERS["protobuf"] = protobuf_serializer  # type: ignore

DESERIALIZERS: Dict[str, Deserializer] = {
    "json": json_deserializer,
    "plain_text": plain_text_deserializer,
    "json_or_text": json_or_text_deserializer,
}

if _PROTOBUF_AVAILABLE:
    DESERIALIZERS["protobuf"] = protobuf_deserializer  # type: ignore

# MIME type mappings used in headers
CONTENT_TYPES: Dict[str, str] = {
    "json": "application/json",
    "plain_text": "text/plain",
}

if _PROTOBUF_AVAILABLE:
    CONTENT_TYPES["protobuf"] = "application/x-protobuf"


def deserializer_for_mime(mime: Optional[str]) -> Deserializer:
    """Return a suitable deserializer for the given content-type.

    Falls back to ``json_or_text`` when unknown or not provided.
    """

    if not mime:
        return DESERIALIZERS["json_or_text"]

    mime_l = mime.lower()
    if "json" in mime_l:
        return DESERIALIZERS["json"]
    if "protobuf" in mime_l and _PROTOBUF_AVAILABLE:
        return DESERIALIZERS["protobuf"]  # type: ignore
    if "text" in mime_l:
        return DESERIALIZERS["plain_text"]
    return DESERIALIZERS["json_or_text"]
