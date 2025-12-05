import json


def test_json_deserializer_valid():
    from serialization.json_format import json_deserializer

    data = {"a": 1, "b": "text"}
    raw = json.dumps(data).encode("utf-8")

    result = json_deserializer(raw)

    assert result == data


def test_json_or_text_deserializer_json_ok():
    from serialization.json_format import json_or_text_deserializer

    payload = {"x": 123}
    raw = json.dumps(payload).encode("utf-8")

    out = json_or_text_deserializer(raw)

    assert out == payload
    assert isinstance(out, dict)


def test_json_or_text_deserializer_invalid_json_falls_back_to_text():
    from serialization.json_format import json_or_text_deserializer

    raw = b"this is not json"

    out = json_or_text_deserializer(raw)

    assert out == "this is not json"
    assert isinstance(out, str)


def test_json_or_text_deserializer_invalid_utf8_replaced():
    from serialization.json_format import json_or_text_deserializer

    raw = b"\xff\xfe\xfd"  # invalid UTF-8

    out = json_or_text_deserializer(raw)

    # Should decode with replacement characters via plain_text_deserializer
    assert isinstance(out, str)
    assert "\ufffd" in out or "�" in out
