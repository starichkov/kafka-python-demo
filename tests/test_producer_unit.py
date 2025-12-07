import os
from unittest.mock import patch, Mock


class FakeProducer:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.sent = []

    def send(self, topic, key=None, value=None, headers=None):
        self.sent.append({
            "topic": topic,
            "key": key,
            "value": value,
            "headers": headers or [],
        })
        return Mock()

    def flush(self):
        return None


def test_producer_warns_and_falls_back_when_format_unavailable(monkeypatch):
    import producer

    # Request an unknown format to trigger fallback path
    monkeypatch.setenv("MESSAGE_FORMAT", "avro")

    # Patch KafkaProducer and time.sleep
    monkeypatch.setattr(producer, "KafkaProducer", FakeProducer, raising=True)
    monkeypatch.setattr(producer.time, "sleep", lambda *_: None, raising=True)

    # Capture logger
    with patch.object(producer, "get_logger") as mock_get_logger:
        logger = Mock()
        mock_get_logger.return_value = logger

        producer_instance = producer.produce_events("localhost:9092", "t")

        # The function does not return the producer; assertions are on logger and FakeProducer via patching
        # Ensure warning about fallback to json was logged
        assert any("falling back to 'json'" in str(c) for c in logger.warning.call_args_list), (
            f"Expected fallback warning, got: {logger.warning.call_args_list}"
        )

        # Verify at least one send used application/json header
        # Access the FakeProducer instance via the last call to KafkaProducer constructor
        # Our FakeProducer doesn't expose directly here; rely on logger.info 'Sent:' calls count as a proxy
        # Better: ensure logger.info startup line contains content-type=application/json
        assert any("content-type=application/json" in str(c) for c in logger.info.call_args_list), (
            f"Expected startup info with application/json, got: {logger.info.call_args_list}"
        )
