import importlib
import pytest


def test_roundtrip_basic_dict():
    pb = pytest.importorskip("serialization.protobuf_format")

    data = {"id": 7, "event_type": "note_created", "text": "hello"}

    raw = pb.protobuf_serializer(data)
    out = pb.protobuf_deserializer(raw)

    assert out == data


def test_serializer_rejects_non_dict():
    pb = pytest.importorskip("serialization.protobuf_format")

    with pytest.raises(TypeError):
        pb.protobuf_serializer([1, 2, 3])


def test_deserialize_empty_defaults():
    pb = pytest.importorskip("serialization.protobuf_format")

    out = pb.protobuf_deserializer(b"")
    assert out == {"id": 0, "event_type": "", "text": ""}


def test_serializer_ignores_extra_and_coerces_types():
    pb = pytest.importorskip("serialization.protobuf_format")

    data = {"id": "5", "event_type": b"note_updated", "text": 123, "extra": "ignored"}
    raw = pb.protobuf_serializer(data)
    out = pb.protobuf_deserializer(raw)

    assert out["id"] == 5
    assert out["event_type"] == "note_updated"
    assert out["text"] == "123"
    assert "extra" not in out


def test_serializer_empty_dict_skips_all_fields():
    pb = pytest.importorskip("serialization.protobuf_format")

    raw = pb.protobuf_serializer({})
    out = pb.protobuf_deserializer(raw)

    # All defaults as no fields set
    assert out == {"id": 0, "event_type": "", "text": ""}


def test_build_message_cls_fallback_module_level(monkeypatch):
    # Force module-level GetMessageClass to raise and ensure factory fallback path works
    pb = pytest.importorskip("serialization.protobuf_format")
    from google.protobuf import message_factory as gmf

    # Capture an already-built class to return from the fake factory
    existing_cls = pb._NoteEvent

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    class FakeFactory:
        def __init__(self, pool):
            self.pool = pool

        def GetMessageClass(self, desc):
            return existing_cls

        def GetPrototype(self, desc):
            return existing_cls

    monkeypatch.setattr(gmf, "GetMessageClass", boom, raising=True)
    monkeypatch.setattr(gmf, "MessageFactory", FakeFactory, raising=True)

    # Reload the module so it re-runs builder with patched factory
    pb2 = importlib.reload(pb)

    data = {"id": 9, "event_type": "x", "text": "y"}
    raw = pb2.protobuf_serializer(data)
    out = pb2.protobuf_deserializer(raw)
    assert out == data


def test_build_message_cls_double_fallback_to_get_prototype(monkeypatch):
    pb = pytest.importorskip("serialization.protobuf_format")
    from google.protobuf import message_factory as gmf

    existing_cls = pb._NoteEvent

    # Patch module-level helper to raise
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    class FakeFactory:
        def __init__(self, pool):
            self.pool = pool

        def GetMessageClass(self, desc):
            # Also raise to force the second fallback
            raise RuntimeError("boom2")

        def GetPrototype(self, desc):
            return existing_cls

    monkeypatch.setattr(gmf, "GetMessageClass", boom, raising=True)
    monkeypatch.setattr(gmf, "MessageFactory", FakeFactory, raising=True)

    pb2 = importlib.reload(pb)

    payload = {"id": 1, "event_type": "proto", "text": "ok"}
    raw = pb2.protobuf_serializer(payload)
    out = pb2.protobuf_deserializer(raw)
    assert out == payload


def test_pool_add_exception_path_is_handled(monkeypatch):
    # Ensure the try/except around pool.Add is covered
    pb = pytest.importorskip("serialization.protobuf_format")
    from google.protobuf import descriptor_pool as gdp
    from google.protobuf import message_factory as gmf

    base_pool = gdp.Default()

    class WrapperPool:
        def Add(self, file_proto):
            # Add to real pool to make descriptor available, then raise to hit except
            base_pool.Add(file_proto)
            raise RuntimeError("duplicate")

        def FindMessageTypeByName(self, name):
            return base_pool.FindMessageTypeByName(name)

    # Return wrapper so Add raises, but descriptor remains available in base_pool
    monkeypatch.setattr(gdp, "Default", lambda: WrapperPool(), raising=True)

    # Keep message factory behavior simple by returning existing class
    existing_cls = pb._NoteEvent

    def fake_get_message_class(desc):
        return existing_cls

    class FakeFactory:
        def __init__(self, pool):
            self.pool = pool
        def GetMessageClass(self, desc):
            return existing_cls
        def GetPrototype(self, desc):
            return existing_cls

    monkeypatch.setattr(gmf, "GetMessageClass", fake_get_message_class, raising=True)
    monkeypatch.setattr(gmf, "MessageFactory", FakeFactory, raising=True)

    # Reload to execute builder with patched pool
    pb2 = importlib.reload(pb)

    out = pb2.protobuf_deserializer(b"")
    assert out == {"id": 0, "event_type": "", "text": ""}
