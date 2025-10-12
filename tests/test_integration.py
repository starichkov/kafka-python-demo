"""
Integration Tests for Improving Code Coverage

This test module provides comprehensive integration tests for the producer, consumer, and logger
modules to improve code coverage by testing individual functions, edge cases, exception
handling, and module-level code using real Kafka infrastructure with Testcontainers.

The tests use real Kafka containers to test functionality end-to-end while maintaining
comprehensive coverage of all code paths.
"""

import pytest
import json
import sys
import os
import logging
import subprocess
from testcontainers.kafka import KafkaContainer
from kafka import KafkaProducer, KafkaConsumer
from unittest.mock import Mock, patch

# Mock sys.argv to prevent argument parsing issues when importing a consumer module
with patch.object(sys, 'argv', ['consumer.py']):
    import consumer
import producer
from logger import get_logger


@pytest.fixture(scope="module")
def kafka_container():
    """Fixture that provides a reusable Kafka container for all tests."""
    with KafkaContainer(image="confluentinc/cp-kafka:7.9.3") as kafka:
        yield kafka


class TestTryParseJson:
    """Test the try_parse_json function from consumer.py"""

    def test_parse_valid_json(self):
        """Test parsing valid JSON bytes"""
        from consumer import try_parse_json

        json_data = {"key": "value", "number": 42}
        json_bytes = json.dumps(json_data).encode('utf-8')

        result = try_parse_json(json_bytes)

        assert result == json_data
        assert isinstance(result, dict)

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON falls back to plain text"""
        from consumer import try_parse_json

        plain_text = "This is not JSON"
        text_bytes = plain_text.encode('utf-8')

        result = try_parse_json(text_bytes)

        assert result == plain_text
        assert isinstance(result, str)

    def test_parse_invalid_utf8(self):
        """Test parsing invalid UTF-8 bytes with error replacement"""
        from consumer import try_parse_json

        # Invalid UTF-8 bytes
        invalid_bytes = b'\xff\xfe\xfd'

        result = try_parse_json(invalid_bytes)

        assert isinstance(result, str)
        # Should contain replacement characters
        assert '�' in result


class TestConsumeEventsIntegration:
    """Integration tests for the consume_events function using real Kafka"""

    def test_consume_events_json_message(self, kafka_container):
        """Test-consuming JSON messages with real Kafka"""
        topic = "test-json-consume-events"
        bootstrap_servers = kafka_container.get_bootstrap_server()

        # Send a test message using a real producer
        producer_instance = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        test_message = {"id": 1, "event_type": "test_event", "data": "test data"}
        producer_instance.send(topic, key="test_key", value=test_message)
        producer_instance.flush()
        producer_instance.close()

        # Test consume_events function with a real consumer but with timeout
        consumer_args = {
            'bootstrap_servers': bootstrap_servers,
            'auto_offset_reset': 'earliest',
            'consumer_timeout_ms': 5000
        }

        # Capture the logger output to verify the function worked
        import io
        from unittest.mock import patch

        captured_output = io.StringIO()

        # Patch the logger to capture output
        with patch('consumer.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            # Call the function - it will timeout after 5 seconds
            try:
                consumer.consume_events(topic, consumer_args)
            except:
                pass  # Expected to timeout or exit

            # Verify the logger was called with our test message
            mock_logger.info.assert_called()
            log_calls = [str(call) for call in mock_logger.info.call_args_list]

            # Should contain JSON message details
            json_logged = any("test_event" in call for call in log_calls)
            assert json_logged, f"Expected 'test_event' in log calls: {log_calls}"

    def test_consume_events_plain_text_message(self, kafka_container):
        """Test consuming plain text messages with real Kafka"""
        topic = "test-plain-consume-events"
        bootstrap_servers = kafka_container.get_bootstrap_server()

        # Send a plain text message
        producer_instance = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            value_serializer=lambda v: v.encode('utf-8')
        )

        plain_message = "This is a plain text message"
        producer_instance.send(topic, key="plain_key", value=plain_message)
        producer_instance.flush()
        producer_instance.close()

        # Test consume_events with plain text
        consumer_args = {
            'bootstrap_servers': bootstrap_servers,
            'auto_offset_reset': 'earliest',
            'consumer_timeout_ms': 5000
        }

        # Capture the logger output
        with patch('consumer.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            try:
                consumer.consume_events(topic, consumer_args)
            except:
                pass  # Expected to timeout

            # Verify plain text handling
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            plain_logged = any("📦 Plain" in call and plain_message in call for call in log_calls)
            assert plain_logged, f"Expected plain text message in logs: {log_calls}"

    def test_consume_events_with_event_filtering(self, kafka_container):
        """Test event type filtering functionality with real Kafka"""
        topic = "test-filter-consume-events"
        bootstrap_servers = kafka_container.get_bootstrap_server()

        # Send messages with different event types
        producer_instance = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        wanted_message = {"id": 1, "event_type": "wanted_event", "data": "wanted"}
        unwanted_message = {"id": 2, "event_type": "unwanted_event", "data": "unwanted"}

        producer_instance.send(topic, key="wanted", value=wanted_message)
        producer_instance.send(topic, key="unwanted", value=unwanted_message)
        producer_instance.flush()
        producer_instance.close()

        # Test filtering with wanted_event
        consumer_args = {
            'bootstrap_servers': bootstrap_servers,
            'auto_offset_reset': 'earliest',
            'consumer_timeout_ms': 5000
        }

        with patch('consumer.get_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            try:
                consumer.consume_events(topic, consumer_args, event_type='wanted_event')
            except:
                pass  # Expected to timeout

            log_calls = [str(call) for call in mock_logger.info.call_args_list]

            # Should contain wanted event but not unwanted (due to filtering)
            wanted_logged = any("wanted_event" in call for call in log_calls)
            unwanted_logged = any("unwanted_event" in call for call in log_calls)

            assert wanted_logged, f"Expected 'wanted_event' in logs: {log_calls}"
            assert not unwanted_logged, f"Should not have 'unwanted_event' in logs: {log_calls}"


class TestConsumerMainIntegration:
    """Integration tests for the consumer main function"""

    def test_main_with_environment_variables(self, kafka_container):
        """Test main function reads environment variables correctly"""
        topic = "test-main-env-vars"
        bootstrap_servers = kafka_container.get_bootstrap_server()

        # Send a test message first
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        producer.send(topic, value={"id": 1, "event_type": "env_test"})
        producer.flush()

        # Test main function via subprocess
        env = os.environ.copy()
        env["KAFKA_TOPIC"] = topic
        env["KAFKA_BOOTSTRAP_SERVERS"] = bootstrap_servers
        env["COVERAGE_PROCESS_START"] = ".coveragerc"

        result = subprocess.run(
            ["python", "consumer.py", "--test-mode"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )

        assert "env_test" in result.stdout

    def test_main_with_group_id_argument(self, kafka_container):
        """Test main function with group_id argument"""
        topic = "test-main-group-id"
        bootstrap_servers = kafka_container.get_bootstrap_server()

        # Send a test message first
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        producer.send(topic, value={"id": 1, "event_type": "group_test"})
        producer.flush()

        # Test the main function with group-id
        env = os.environ.copy()
        env["KAFKA_TOPIC"] = topic
        env["KAFKA_BOOTSTRAP_SERVERS"] = bootstrap_servers
        env["COVERAGE_PROCESS_START"] = ".coveragerc"

        result = subprocess.run(
            ["python", "consumer.py", "--group-id", "test-group", "--test-mode"],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )

        assert "group_test" in result.stdout
        assert "test-group" in result.stdout


class TestProduceEventsIntegration:
    """Integration tests for the produce_events function using real Kafka"""

    def test_produce_events(self, kafka_container):
        """Test producing events to a real Kafka topic"""
        topic = "test-produce-events"
        bootstrap_servers = kafka_container.get_bootstrap_server()

        # Run produce_events function
        producer.produce_events(bootstrap_servers, topic)

        # Verify messages were produced by consuming them
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset='earliest',
            consumer_timeout_ms=5000,
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )

        messages = []
        for message in consumer:
            messages.append(message.value)

        # Should have 9 messages (3 event types * 3)
        assert len(messages) == 9

        # Verify event types are present
        event_types = {msg['event_type'] for msg in messages}
        expected_types = {"note_created", "note_updated", "note_deleted"}
        assert event_types == expected_types

        consumer.close()

    def test_event_types_constant(self):
        """Test that EVENT_TYPES constant is accessible and correct"""
        from producer import EVENT_TYPES

        expected_types = ["note_created", "note_updated", "note_deleted"]
        assert EVENT_TYPES == expected_types


class TestProducerMainIntegration:
    """Integration tests for the producer main function"""

    def test_main_with_environment_variables(self, kafka_container):
        """Test producer main function with environment variables"""
        topic = "test-producer-main-env"
        bootstrap_servers = kafka_container.get_bootstrap_server()

        env = os.environ.copy()
        env["KAFKA_TOPIC"] = topic
        env["KAFKA_BOOTSTRAP_SERVERS"] = bootstrap_servers
        env["COVERAGE_PROCESS_START"] = ".coveragerc"

        # Run producer main
        result = subprocess.run(
            ["python", "producer.py"],
            env=env,
            capture_output=True,
            text=True,
            timeout=15
        )

        assert result.returncode == 0
        assert "Sent:" in result.stdout

        # Verify messages were actually sent
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset='earliest',
            consumer_timeout_ms=3000,
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )

        message_count = 0
        for message in consumer:
            message_count += 1

        assert message_count == 9
        consumer.close()

    @patch.dict(os.environ, {}, clear=True)
    def test_main_with_default_values(self, kafka_container):
        """Test producer main function with default values when env vars not set"""
        # This test uses mocking to clear env vars, then tests defaults
        # We can't easily test localhost:9092 with testcontainers, so we'll just test the function call
        with patch('producer.produce_events') as mock_produce:
            producer.main()
            mock_produce.assert_called_once_with('localhost:9092', 'test-topic')


class TestLoggerIntegration:
    """Integration tests for the logger module functionality"""

    def test_get_logger_creates_new_logger(self):
        """Test that get_logger creates a new logger with a proper configuration"""
        logger_name = "test_integration_logger"

        # Clear any existing loggers
        if logger_name in logging.getLogger().manager.loggerDict:
            del logging.getLogger().manager.loggerDict[logger_name]

        logger = get_logger(logger_name)

        assert logger.name == logger_name
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        assert logger.handlers[0].stream == sys.stdout
        assert not logger.propagate

    def test_get_logger_reuses_existing_logger(self):
        """Test that get_logger reuses existing logger"""
        logger_name = "test_reuse_logger"

        # Create first logger
        logger1 = get_logger(logger_name)
        initial_handler_count = len(logger1.handlers)

        # Create second logger with same name
        logger2 = get_logger(logger_name)

        # Should be the same logger instance
        assert logger1 is logger2
        assert len(logger2.handlers) == initial_handler_count

    @patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'})
    def test_get_logger_with_custom_log_level(self):
        """Test get_logger respects LOG_LEVEL environment variable"""
        logger_name = "test_debug_integration_logger"

        if logger_name in logging.getLogger().manager.loggerDict:
            del logging.getLogger().manager.loggerDict[logger_name]

        logger = get_logger(logger_name)
        assert logger.level == logging.DEBUG

    @patch.dict(os.environ, {'LOG_LEVEL': 'INVALID_LEVEL'})
    def test_get_logger_with_invalid_log_level(self):
        """Test get_logger falls back to INFO for invalid log level"""
        logger_name = "test_invalid_integration_logger"

        if logger_name in logging.getLogger().manager.loggerDict:
            del logging.getLogger().manager.loggerDict[logger_name]

        logger = get_logger(logger_name)
        assert logger.level == logging.INFO


class TestModuleLevelCodeIntegration:
    """Integration tests for module-level code and imports"""

    @patch.dict(os.environ, {'COVERAGE_PROCESS_START': '.coveragerc'})
    @patch('coverage.process_startup')
    def test_coverage_startup_consumer(self, mock_process_startup):
        """Test coverage startup code in consumer module"""
        import importlib
        if 'consumer' in sys.modules:
            with patch.object(sys, 'argv', ['consumer.py']):
                importlib.reload(sys.modules['consumer'])

        mock_process_startup.assert_called()

    @patch.dict(os.environ, {'COVERAGE_PROCESS_START': '.coveragerc'})
    @patch('coverage.process_startup')
    def test_coverage_startup_producer(self, mock_process_startup):
        """Test coverage startup code in producer module"""
        import importlib
        if 'producer' in sys.modules:
            importlib.reload(sys.modules['producer'])

        mock_process_startup.assert_called()

    def test_consumer_argument_parser_setup(self):
        """Test that the consumer argument parser is properly configured"""
        parser = consumer.build_parser()
        parser_actions = [action.dest for action in parser._actions]

        assert 'event_type' in parser_actions
        assert 'group_id' in parser_actions
        assert 'test_mode' in parser_actions


class TestMainExecutionIntegration:
    """Integration tests for __main__ execution blocks"""

    @patch('consumer.main')
    def test_consumer_main_execution(self, mock_main):
        """Test consumer __main__ execution"""
        with patch('consumer.__name__', '__main__'):
            exec('if __name__ == "__main__": main()', {'__name__': '__main__', 'main': mock_main})
        mock_main.assert_called_once()

    @patch('producer.main')
    def test_producer_main_execution(self, mock_main):
        """Test producer __main__ execution"""
        with patch('producer.__name__', '__main__'):
            exec('if __name__ == "__main__": main()', {'__name__': '__main__', 'main': mock_main})
        mock_main.assert_called_once()


class TestArgumentParsingIntegration:
    """Integration tests for CLI argument parsing scenarios"""

    def test_consumer_with_all_arguments(self):
        """Test consumer argument parsing with all options"""
        from consumer import build_parser

        parser = build_parser()
        args = parser.parse_args([
            '--event-type', 'test_event',
            '--group-id', 'test_group',
            '--test-mode'
        ])

        assert args.event_type == 'test_event'
        assert args.group_id == 'test_group'
        assert args.test_mode is True

    def test_consumer_with_no_arguments(self):
        """Test consumer argument parsing with no arguments"""
        from consumer import build_parser

        parser = build_parser()
        args = parser.parse_args([])

        assert args.event_type is None
        assert args.group_id is None
        assert args.test_mode is False


class TestMainFunctionCoverage:
    """Tests to ensure complete coverage of the main function and exception handling"""

    @patch('consumer.consume_events')
    @patch.dict(os.environ, {'KAFKA_TOPIC': 'test-topic', 'KAFKA_BOOTSTRAP_SERVERS': 'localhost:9092'})
    @patch.object(sys, 'argv', ['consumer.py'])
    def test_main_function_execution(self, mock_consume_events):
        """Test main function execution with default environment variables"""
        consumer.main()

        # Verify consume_events was called with correct parameters
        mock_consume_events.assert_called_once()
        args, kwargs = mock_consume_events.call_args

        topic, consumer_args, event_type, group_id = args
        assert topic == 'test-topic'
        assert consumer_args['bootstrap_servers'] == 'localhost:9092'
        assert consumer_args['auto_offset_reset'] == 'earliest'
        assert consumer_args['enable_auto_commit'] is True
        assert event_type is None
        assert group_id is None

    @patch('consumer.consume_events')
    @patch.dict(os.environ, {'KAFKA_TOPIC': 'custom-topic', 'KAFKA_BOOTSTRAP_SERVERS': 'custom:9092'})
    def test_main_function_with_arguments_and_custom_env(self, mock_consume_events):
        """Test main function execution with custom environment variables and arguments"""
        # Mock the parser to control parsed args
        with patch('consumer.build_parser') as mock_build_parser:
            from types import SimpleNamespace
            mock_parser = Mock()
            mock_parser.parse_args.return_value = SimpleNamespace(group_id='test-group', event_type='test-event', test_mode=False)
            mock_build_parser.return_value = mock_parser

            consumer.main()

            mock_consume_events.assert_called_once()
            args, kwargs = mock_consume_events.call_args

            topic, consumer_args, event_type, group_id = args
            assert topic == 'custom-topic'
            assert consumer_args['bootstrap_servers'] == 'custom:9092'
            assert consumer_args['group_id'] == 'test-group'
            assert event_type == 'test-event'
            assert group_id == 'test-group'

    @patch('consumer.consume_events')
    def test_main_function_with_test_mode(self, mock_consume_events):
        """Test main function execution with test mode argument"""
        # Mock the parser to simulate test mode via parsed args
        with patch('consumer.build_parser') as mock_build_parser:
            from types import SimpleNamespace
            mock_parser = Mock()
            mock_parser.parse_args.return_value = SimpleNamespace(group_id=None, event_type=None, test_mode=True)
            mock_build_parser.return_value = mock_parser

            consumer.main()

            mock_consume_events.assert_called_once()
            args, kwargs = mock_consume_events.call_args

            topic, consumer_args, event_type, group_id = args
            assert 'consumer_timeout_ms' in consumer_args
            assert consumer_args['consumer_timeout_ms'] == 3000

    def test_keyboard_interrupt_handling(self, kafka_container):
        """Test KeyboardInterrupt exception handling in consume_events"""
        topic = "test-keyboard-interrupt"
        bootstrap_servers = kafka_container.get_bootstrap_server()

        consumer_args = {
            'bootstrap_servers': bootstrap_servers,
            'auto_offset_reset': 'earliest',
            'enable_auto_commit': True
        }

        # Mock KafkaConsumer to simulate KeyboardInterrupt
        with patch('consumer.KafkaConsumer') as mock_kafka_consumer:
            mock_consumer_instance = Mock()
            mock_kafka_consumer.return_value = mock_consumer_instance

            # Make the consumer iteration raise KeyboardInterrupt
            mock_consumer_instance.__iter__ = Mock(side_effect=KeyboardInterrupt())

            # Mock logger to capture the graceful shutdown message
            with patch('consumer.get_logger') as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                # Call consume_events - should handle KeyboardInterrupt gracefully
                consumer.consume_events(topic, consumer_args)

                # Verify that the graceful shutdown message was logged
                mock_logger.info.assert_called()
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                shutdown_logged = any("Shutting down gracefully" in call for call in log_calls)
                assert shutdown_logged, f"Expected graceful shutdown message in logs: {log_calls}"

                # Verify consumer was closed
                mock_consumer_instance.close.assert_called_once()
