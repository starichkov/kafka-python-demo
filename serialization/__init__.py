from typing import Any, Callable, Dict

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

SERIALIZERS: Dict[str, Serializer] = {
    "json": json_serializer,
}

DESERIALIZERS: Dict[str, Deserializer] = {
    "json": json_deserializer,
    "plain_text": plain_text_deserializer,
    "json_or_text": json_or_text_deserializer,
}
