import json
from types import SimpleNamespace
from unittest.mock import patch, Mock


class FakeMessage(SimpleNamespace):
    pass


class FakeConsumer:
    def __init__(self, messages, raise_keyboard=False):
        self._iter = iter(messages)
        self._raise_keyboard = raise_keyboard
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self._iter)
        except StopIteration:
            if self._raise_keyboard:
                # Raise KeyboardInterrupt to exercise graceful shutdown path
                self._raise_keyboard = False
                raise KeyboardInterrupt
            raise

    def close(self):
        self.closed = True


def _build_msg(value_bytes, key="k", partition=0, offset=0, headers=None):
    return FakeMessage(value=value_bytes, key=(key.encode("utf-8") if key else None), partition=partition, offset=offset, headers=headers or [])


def test_consume_unknown_mime_falls_back_to_plain_text():
    import consumer

    # Header with bytes key and unknown mime
    headers = [(b"content-type", b"application/x-unknown")]
    msg = _build_msg(b"this is not json", headers=headers)

    fake = FakeConsumer([msg])

    with patch.object(consumer, "KafkaConsumer", return_value=fake), patch.object(consumer, "get_logger") as mock_get_logger:
        logger = Mock()
        mock_get_logger.return_value = logger

        # No timeout since fake iterator ends immediately
        consumer.consume_events("t", {"bootstrap_servers": "dummy"})

        calls = [str(c) for c in logger.info.call_args_list]
        assert any("\ud83d\udce6 Plain" in c or "📦 Plain" in c for c in calls), f"Expected Plain log, got: {calls}"


def test_consume_protobuf_mime_with_invalid_bytes_falls_back_to_plain_text():
    import consumer

    headers = [("content-type", b"application/x-protobuf")]
    # Not a valid NoteEvent protobuf payload → forces parser exception
    msg = _build_msg(b"\x08\xff", headers=headers)

    fake = FakeConsumer([msg])

    with patch.object(consumer, "KafkaConsumer", return_value=fake), patch.object(consumer, "get_logger") as mock_get_logger:
        logger = Mock()
        mock_get_logger.return_value = logger

        consumer.consume_events("t", {"bootstrap_servers": "dummy"})

        calls = [str(c) for c in logger.info.call_args_list]
        assert any("Plain" in c for c in calls), f"Expected Plain log, got: {calls}"


def test_event_filtering_skips_non_matching_and_handles_keyboard_interrupt():
    import consumer

    # Two JSON messages: one non-matching event_type, one matching
    m1 = _build_msg(json.dumps({"id": 1, "event_type": "a", "text": "x"}).encode("utf-8"))
    m2 = _build_msg(json.dumps({"id": 2, "event_type": "b", "text": "y"}).encode("utf-8"))

    # After messages, raise KeyboardInterrupt to exercise except branch
    fake = FakeConsumer([m1, m2], raise_keyboard=True)

    with patch.object(consumer, "KafkaConsumer", return_value=fake), patch.object(consumer, "get_logger") as mock_get_logger:
        logger = Mock()
        mock_get_logger.return_value = logger

        consumer.consume_events("t", {"bootstrap_servers": "dummy"}, event_type="b", group_id="g")

        # Only the matching event should be logged with JSON (...)
        calls = [str(c) for c in logger.info.call_args_list]
        json_calls = [c for c in calls if "JSON (" in c]
        assert len(json_calls) >= 1
        assert any("(b)" in c for c in json_calls)
        # Graceful shutdown message should be present due to KeyboardInterrupt
        assert any("Shutting down gracefully" in c for c in calls)
