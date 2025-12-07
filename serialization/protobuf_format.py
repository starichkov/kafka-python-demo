from typing import Any, Dict

"""Protobuf serialization utilities for Note events.

This module defines a minimal Protobuf schema for a NoteEvent message at
runtime (without requiring a separate .proto compilation step). It provides
helpers to serialize Python dicts to Protobuf bytes and deserialize bytes
back to dicts.
"""

from google.protobuf import descriptor_pb2
from google.protobuf import descriptor_pool
from google.protobuf import message_factory


def _build_note_event_message_cls():
    # Define a simple NoteEvent message with three fields.
    file_proto = descriptor_pb2.FileDescriptorProto()
    file_proto.name = "note_event.proto"
    file_proto.package = "notes"

    message_proto = file_proto.message_type.add()
    message_proto.name = "NoteEvent"

    # int32 id = 1;
    field_id = message_proto.field.add()
    field_id.name = "id"
    field_id.number = 1
    field_id.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    field_id.type = descriptor_pb2.FieldDescriptorProto.TYPE_INT32

    # string event_type = 2;
    field_event_type = message_proto.field.add()
    field_event_type.name = "event_type"
    field_event_type.number = 2
    field_event_type.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    field_event_type.type = descriptor_pb2.FieldDescriptorProto.TYPE_STRING

    # string text = 3;
    field_text = message_proto.field.add()
    field_text.name = "text"
    field_text.number = 3
    field_text.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    field_text.type = descriptor_pb2.FieldDescriptorProto.TYPE_STRING

    pool = descriptor_pool.Default()
    try:
        pool.Add(file_proto)
    except Exception:
        # If already added (e.g., due to test reloads), ignore.
        pass

    desc = pool.FindMessageTypeByName("notes.NoteEvent")
    # Protobuf v6 prefers GetMessageClass; older versions use GetPrototype
    try:  # Prefer module-level helper if available (v6+)
        cls = message_factory.GetMessageClass(desc)  # type: ignore[attr-defined]
    except Exception:
        factory = message_factory.MessageFactory(pool)
        try:
            cls = factory.GetMessageClass(desc)  # type: ignore[attr-defined]
        except Exception:
            cls = factory.GetPrototype(desc)
    return cls


_NoteEvent = _build_note_event_message_cls()


def _dict_to_message(d: Dict[str, Any]):
    msg = _NoteEvent()
    if "id" in d and d["id"] is not None:
        msg.id = int(d["id"])  # type: ignore[attr-defined]
    if "event_type" in d and d["event_type"] is not None:
        ev = d["event_type"]
        if isinstance(ev, (bytes, bytearray)):
            msg.event_type = ev.decode("utf-8", errors="replace")  # type: ignore[attr-defined]
        else:
            msg.event_type = str(ev)  # type: ignore[attr-defined]
    if "text" in d and d["text"] is not None:
        tx = d["text"]
        if isinstance(tx, (bytes, bytearray)):
            msg.text = tx.decode("utf-8", errors="replace")  # type: ignore[attr-defined]
        else:
            msg.text = str(tx)  # type: ignore[attr-defined]
    return msg


def _message_to_dict(msg) -> Dict[str, Any]:
    # Convert only known fields
    return {
        "id": int(getattr(msg, "id", 0)),
        "event_type": str(getattr(msg, "event_type", "")),
        "text": str(getattr(msg, "text", "")),
    }


def protobuf_serializer(value: Any) -> bytes:
    """Serialize a Python dict NoteEvent to Protobuf bytes.

    The input is expected to be a dict with keys: id, event_type, text.
    Extra keys are ignored.
    """
    if not isinstance(value, dict):
        raise TypeError("protobuf_serializer expects a dict")
    msg = _dict_to_message(value)
    return msg.SerializeToString()


def protobuf_deserializer(value: bytes) -> Any:
    """Deserialize Protobuf bytes of NoteEvent into a Python dict."""
    msg = _NoteEvent()
    msg.ParseFromString(value)
    return _message_to_dict(msg)
