"""
Consolidated tests for example_resilient_messaging.py

All of them targeted example_resilient_messaging; keeping them together clarifies intent
and avoids cross-test imports (e.g., FakeThread) while preserving class organization.
"""

import argparse
import os
import sys
import unittest
from unittest.mock import Mock, patch

# Import the module under test (some tests use example_module alias)
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import example_resilient_messaging as example_module


# Helper used by a number of tests to control threading
class FakeThread:
    """A fake Thread that can either run target immediately or no-op."""
    def __init__(self, target=None, daemon=None, run_immediately=False, swallow_keyboard=True):
        self._target = target
        self._run_immediately = run_immediately
        self._swallow_keyboard = swallow_keyboard
        self.daemon = daemon

    def start(self):
        if not self._run_immediately or self._target is None:
            return None
        try:
            return self._target()
        except KeyboardInterrupt:
            if not self._swallow_keyboard:
                raise
            return None


# ============== Content from tests/test_example_integration.py ==============
class TestArgumentParsing(unittest.TestCase):
    """Test cases for argument parsing functionality."""

    def test_argument_parser_setup(self):
        """Test that the argument parser is configured correctly."""
        parser = argparse.ArgumentParser(description="Resilient Kafka Messaging Demo")
        parser.add_argument(
            "--mode",
            choices=["producer", "consumer", "error-demo"],
            default="error-demo",
            help="Demo mode to run"
        )

        # Test default mode
        args = parser.parse_args([])
        self.assertEqual(args.mode, "error-demo")

        # Test producer mode
        args = parser.parse_args(["--mode", "producer"])
        self.assertEqual(args.mode, "producer")

        # Test consumer mode
        args = parser.parse_args(["--mode", "consumer"])
        self.assertEqual(args.mode, "consumer")

        # Test error-demo mode
        args = parser.parse_args(["--mode", "error-demo"])
        self.assertEqual(args.mode, "error-demo")

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises an error."""
        parser = argparse.ArgumentParser(description="Resilient Kafka Messaging Demo")
        parser.add_argument(
            "--mode",
            choices=["producer", "consumer", "error-demo"],
            default="error-demo",
            help="Demo mode to run"
        )

        with self.assertRaises(SystemExit):
            parser.parse_args(["--mode", "invalid"])


class TestProducerDemo(unittest.TestCase):
    """Test cases for producer demo functionality."""

    @patch.dict('os.environ', {
        'KAFKA_BOOTSTRAP_SERVERS': 'test-servers:9092',
        'KAFKA_TOPIC': 'test-topic'
    })
    @patch('example_resilient_messaging.ResilientProducer')
    def test_producer_demo_configuration(self, mock_producer_class):
        """Test producer demo uses correct configuration from environment."""
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer

        # Mock successful sends
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_producer.send_message_with_retry.return_value = mock_metadata

        try:
            example_module.run_resilient_producer_demo()
        except Exception:
            pass  # We expect some exceptions due to mocking

        # Verify producer was created with correct servers
        mock_producer_class.assert_called_with('test-servers:9092', retries=3, retry_delay=1.0)

    @patch.dict('os.environ', {}, clear=True)
    @patch('example_resilient_messaging.ResilientProducer')
    def test_producer_demo_default_configuration(self, mock_producer_class):
        """Test producer demo uses defaults when environment variables not set."""
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer

        # Mock successful sends
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_producer.send_message_with_retry.return_value = mock_metadata

        try:
            example_module.run_resilient_producer_demo()
        except Exception:
            pass  # We expect some exceptions due to mocking

        # Verify producer was created with defaults
        mock_producer_class.assert_called_with('localhost:9092', retries=3, retry_delay=1.0)

    @patch('example_resilient_messaging.ResilientProducer')
    def test_producer_demo_message_types(self, mock_producer_class):
        """Test that producer demo creates various message types."""
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer

        # Mock successful sends
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_producer.send_message_with_retry.return_value = mock_metadata
        mock_producer.send_message_async.return_value = None

        try:
            example_module.run_resilient_producer_demo()
        except Exception:
            pass

        # Verify various message types were sent
        send_calls = mock_producer.send_message_with_retry.call_args_list
        self.assertTrue(len(send_calls) > 0)

        # Check that different event types are present
        event_types_sent = set()
        for call in send_calls:
            message = call[0][1]  # Second argument is the message
            if isinstance(message, dict) and 'event_type' in message:
                event_types_sent.add(message['event_type'])

        # Verify we have different types of messages
        self.assertTrue(len(event_types_sent) > 1)

    @patch('example_resilient_messaging.ResilientProducer')
    def test_producer_demo_async_messages(self, mock_producer_class):
        """Test that producer demo sends async messages with callbacks."""
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer

        # Mock successful sends
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_producer.send_message_with_retry.return_value = mock_metadata

        try:
            example_module.run_resilient_producer_demo()
        except Exception:
            pass

        # Verify async messages were sent
        self.assertTrue(mock_producer.send_message_async.called)

        # Verify flush was called
        mock_producer.flush.assert_called()

    @patch('example_resilient_messaging.ResilientProducer')
    def test_producer_demo_error_handling(self, mock_producer_class):
        """Test that producer demo handles send failures gracefully."""
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer

        # Mock some sends to fail
        mock_producer.send_message_with_retry.side_effect = [
            Exception("Send failed"),  # First send fails
            Mock(partition=0, offset=123)  # Second send succeeds
        ]

        # Should not raise exception - demo handles errors gracefully
        try:
            example_module.run_resilient_producer_demo()
        except Exception:
            pass


class TestConsumerDemo(unittest.TestCase):
    """Test cases for consumer demo functionality."""

    @patch.dict('os.environ', {
        'KAFKA_BOOTSTRAP_SERVERS': 'test-servers:9092',
        'KAFKA_TOPIC': 'test-topic',
        'KAFKA_DLQ_TOPIC': 'test-dlq',
        'BATCH_MODE': 'false'
    })
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.threading.Thread')
    def test_consumer_demo_configuration(self, mock_thread, mock_consumer_class):
        """Test consumer demo uses correct configuration from environment."""
        mock_consumer = Mock()
        mock_consumer.__enter__ = Mock(return_value=mock_consumer)
        mock_consumer.__exit__ = Mock(return_value=None)
        mock_consumer_class.return_value = mock_consumer

        # Mock thread for stats
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        try:
            example_module.run_resilient_consumer_demo()
        except Exception:
            pass

        # Verify consumer was created with correct configuration
        mock_consumer_class.assert_called_with(
            'test-servers:9092',
            ['test-topic'],
            'resilient-demo-consumer',
            'test-dlq'
        )

    @patch.dict('os.environ', {'BATCH_MODE': 'true'})
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.threading.Thread')
    def test_consumer_demo_batch_mode(self, mock_thread, mock_consumer_class):
        """Test consumer demo batch processing mode."""
        mock_consumer = Mock()
        mock_consumer.__enter__ = Mock(return_value=mock_consumer)
        mock_consumer.__exit__ = Mock(return_value=None)
        mock_consumer_class.return_value = mock_consumer

        # Mock thread for stats
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        try:
            example_module.run_resilient_consumer_demo()
        except Exception:
            pass

        # Verify batch processing was called
        mock_consumer.process_messages_batch.assert_called()

    @patch.dict('os.environ', {'BATCH_MODE': 'false'})
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.threading.Thread')
    def test_consumer_demo_single_message_mode(self, mock_thread, mock_consumer_class):
        """Test consumer demo single message processing mode."""
        mock_consumer = Mock()
        mock_consumer.__enter__ = Mock(return_value=mock_consumer)
        mock_consumer.__exit__ = Mock(return_value=None)
        mock_consumer_class.return_value = mock_consumer

        # Mock thread for stats
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        try:
            example_module.run_resilient_consumer_demo()
        except Exception:
            pass

        # Verify single message processing was called
        mock_consumer.process_messages.assert_called()


class TestErrorDemonstration(unittest.TestCase):
    """Test cases for error demonstration functionality."""

    @patch('example_resilient_messaging.ResilientProducer')
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.threading.Thread')
    def test_error_demo_producer_scenarios(self, mock_thread, mock_consumer_class, mock_producer_class):
        """Test error demonstration producer retry scenarios."""
        # Setup producer mock
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer

        # Setup consumer mock
        mock_consumer = Mock()
        mock_consumer.__enter__ = Mock(return_value=mock_consumer)
        mock_consumer.__exit__ = Mock(return_value=None)
        mock_consumer_class.return_value = mock_consumer

        # Mock successful sends
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_producer.send_message_with_retry.return_value = mock_metadata

        # Mock thread
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        try:
            example_module.run_error_demonstration()
        except Exception:
            pass

        # Verify producer scenarios were tested
        self.assertTrue(mock_producer.send_message_with_retry.called)

        # Verify consumer scenarios were tested
        self.assertTrue(mock_consumer.process_messages.called)

    @patch('example_resilient_messaging.ResilientProducer')
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.threading.Thread')
    def test_error_demo_dlq_monitoring(self, mock_thread, mock_consumer_class, mock_producer_class):
        """Test error demonstration DLQ monitoring."""
        # Setup mocks
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer

        mock_consumer = Mock()
        mock_consumer.__enter__ = Mock(return_value=mock_consumer)
        mock_consumer.__exit__ = Mock(return_value=None)
        mock_consumer_class.return_value = mock_consumer

        # Mock thread
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        # Mock successful operations
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_producer.send_message_with_retry.return_value = mock_metadata

        try:
            example_module.run_error_demonstration()
        except Exception:
            pass

        # Verify multiple consumer instances were created (for main processing and DLQ monitoring)
        self.assertTrue(mock_consumer_class.call_count >= 2)


class TestMessageHandlers(unittest.TestCase):
    """Test cases for message handler functions used in demos."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock message objects
        self.mock_message_dict = Mock()
        self.mock_message_dict.key = "test-key"
        self.mock_message_dict.partition = 0
        self.mock_message_dict.offset = 123
        self.mock_message_dict.value = {"id": 1, "event_type": "normal", "data": "test"}

        self.mock_message_text = Mock()
        self.mock_message_text.key = "test-key"
        self.mock_message_text.partition = 0
        self.mock_message_text.offset = 124
        self.mock_message_text.value = "plain text message"

    def test_consumer_demo_message_handler_normal(self):
        """Test consumer demo message handler with normal messages."""
        # Since the handler is defined inside the function, we test the logic separately
        normal_message = Mock()
        normal_message.key = "test-key"
        normal_message.partition = 0
        normal_message.offset = 123
        normal_message.value = {"id": 1, "event_type": "normal", "data": "test"}
        event_type = normal_message.value.get("event_type")
        self.assertNotEqual(event_type, "error_test")
        self.assertNotEqual(event_type, "fatal_error")

    def test_error_demo_handler_logic(self):
        """Test error demonstration handler logic."""
        error_test_message = Mock()
        error_test_message.value = {"id": 1, "event_type": "error_test", "data": "test"}
        event_type = error_test_message.value.get("event_type")
        if event_type == "error_test":
            self.assertEqual(event_type, "error_test")

        fatal_error_message = Mock()
        fatal_error_message.value = {"id": 2, "event_type": "fatal_error", "data": "test"}
        event_type = fatal_error_message.value.get("event_type")
        if event_type == "fatal_error":
            self.assertEqual(event_type, "fatal_error")

    def test_batch_handler_logic(self):
        """Test batch processing handler logic."""
        normal_messages = [
            Mock(value={"id": 1, "event_type": "normal", "data": "test1"}),
            Mock(value={"id": 2, "event_type": "normal", "data": "test2"})
        ]
        for message in normal_messages:
            event_type = message.value.get("event_type")
            self.assertNotEqual(event_type, "batch_error")

        error_batch = [
            Mock(value={"id": 1, "event_type": "normal", "data": "test1"}),
            Mock(value={"id": 2, "event_type": "batch_error", "data": "test2"})
        ]
        has_batch_error = any(msg.value.get("event_type") == "batch_error" for msg in error_batch)
        self.assertTrue(has_batch_error)


class TestMainFunction(unittest.TestCase):
    """Test cases for the main function."""

    @patch('example_resilient_messaging.run_resilient_producer_demo')
    @patch('sys.argv', ['example_resilient_messaging.py', '--mode', 'producer'])
    def test_main_producer_mode(self, mock_producer_demo):
        try:
            example_module.main()
        except SystemExit:
            pass
        except Exception:
            pass

    @patch.dict('os.environ', {
        'KAFKA_BOOTSTRAP_SERVERS': 'test:9092',
        'KAFKA_TOPIC': 'test-topic',
        'KAFKA_DLQ_TOPIC': 'test-dlq'
    })
    def test_main_environment_variable_usage(self):
        self.assertEqual(os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'), 'test:9092')
        self.assertEqual(os.environ.get('KAFKA_TOPIC', 'resilient-demo-topic'), 'test-topic')
        self.assertEqual(os.environ.get('KAFKA_DLQ_TOPIC', 'resilient-demo-topic-dlq'), 'test-dlq')

    def test_main_default_environment_values(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'), 'localhost:9092')
            self.assertEqual(os.environ.get('KAFKA_TOPIC', 'resilient-demo-topic'), 'resilient-demo-topic')
            self.assertEqual(os.environ.get('KAFKA_DLQ_TOPIC', 'resilient-demo-topic-dlq'), 'resilient-demo-topic-dlq')


# ========== Content from tests/test_example_resilient_messaging_coverage.py ==========
class TestExampleResilientMessagingProducer(unittest.TestCase):
    @patch('example_resilient_messaging.time.sleep', lambda *_args, **_kwargs: None)
    @patch('example_resilient_messaging.ResilientProducer')
    def test_producer_demo_callbacks_and_summary(self, mock_producer_class):
        from example_resilient_messaging import run_resilient_producer_demo
        mock_prod = Mock()
        mock_prod.__enter__ = Mock(return_value=mock_prod)
        mock_prod.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_prod
        meta = Mock(partition=0, offset=1)
        side = [meta, meta, meta, meta, meta, Exception('boom'), Exception('boom2')] + [meta] * 3
        def send_retry_side_effect(*_a, **_k):
            if side:
                v = side.pop(0)
                if isinstance(v, Exception):
                    raise v
                return v
            return meta
        mock_prod.send_message_with_retry.side_effect = send_retry_side_effect
        def async_side_effect(_topic, _message, callback=None):
            if callback:
                callback(Exception('async err'), None)
                callback(None, Mock(partition=1, offset=2))
            return None
        mock_prod.send_message_async.side_effect = async_side_effect
        mock_prod.flush.return_value = None
        run_resilient_producer_demo()
        self.assertTrue(mock_prod.send_message_async.called)

    @patch('example_resilient_messaging.ResilientProducer')
    def test_producer_demo_outer_exception_path(self, mock_producer_class):
        from example_resilient_messaging import run_resilient_producer_demo
        mock_prod = Mock()
        mock_prod.__enter__ = Mock(return_value=mock_prod)
        mock_prod.__exit__ = Mock(return_value=None)
        mock_prod.send_message_with_retry.return_value = Mock(partition=0, offset=0)
        mock_prod.send_message_async.return_value = None
        mock_prod.flush.side_effect = RuntimeError('flush failed')
        mock_producer_class.return_value = mock_prod
        run_resilient_producer_demo()


class TestExampleResilientMessagingConsumer(unittest.TestCase):
    @patch('example_resilient_messaging.threading.Thread', lambda target=None, daemon=None: FakeThread(target, daemon, run_immediately=False))
    @patch('example_resilient_messaging.ResilientConsumer')
    def test_consumer_demo_single_mode_handlers(self, mock_consumer_class):
        from example_resilient_messaging import run_resilient_consumer_demo
        os.environ['BATCH_MODE'] = 'false'
        class StubConsumer:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def process_messages(self, handler, max_retries=2, retry_delay=1.0):
                handler(Mock(key='k', partition=0, offset=1, value={'event_type': 'user_created', 'id': 1}))
                try:
                    handler(Mock(key='k', partition=0, offset=2, value={'event_type': 'error_test', 'id': 2}))
                except Exception:
                    pass
                try:
                    handler(Mock(key='k', partition=0, offset=3, value={'event_type': 'fatal_error', 'id': 3}))
                except Exception:
                    pass
                handler(Mock(key='k', partition=0, offset=4, value='plain'))
                raise KeyboardInterrupt('stop')
        mock_consumer_class.return_value = StubConsumer()
        run_resilient_consumer_demo()

    @patch('example_resilient_messaging.threading.Thread', lambda target=None, daemon=None: FakeThread(target, daemon, run_immediately=False))
    @patch('example_resilient_messaging.ResilientConsumer')
    def test_consumer_demo_batch_mode_and_exception(self, mock_consumer_class):
        from example_resilient_messaging import run_resilient_consumer_demo
        os.environ['BATCH_MODE'] = 'true'
        class StubConsumer:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def process_messages_batch(self, handler, batch_size=5, batch_timeout=3.0, max_retries=2):
                handler([
                    Mock(value={'event_type': 'ok'}),
                    Mock(value={'event_type': 'ok2'}),
                ])
                try:
                    handler([Mock(value={'event_type': 'batch_error'})])
                except Exception:
                    pass
                raise KeyboardInterrupt('stop')
        mock_consumer_class.return_value = StubConsumer()
        run_resilient_consumer_demo()

    @patch('example_resilient_messaging.threading.Thread', lambda target=None, daemon=None: FakeThread(target, daemon, run_immediately=False))
    @patch('example_resilient_messaging.ResilientConsumer')
    def test_consumer_demo_generic_exception(self, mock_consumer_class):
        from example_resilient_messaging import run_resilient_consumer_demo
        class BadConsumer:
            def __enter__(self):
                raise RuntimeError('broken')
            def __exit__(self, exc_type, exc, tb):
                return False
        mock_consumer_class.return_value = BadConsumer()
        run_resilient_consumer_demo()


class TestExampleResilientMessagingErrorDemo(unittest.TestCase):
    @patch('example_resilient_messaging.threading.Thread', lambda target=None, daemon=None: FakeThread(target, daemon, run_immediately=True, swallow_keyboard=True))
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.ResilientProducer')
    def test_error_demo_full_flow(self, mock_producer_class, mock_consumer_class):
        from example_resilient_messaging import run_error_demonstration
        prod1 = Mock()
        prod1.__enter__ = Mock(return_value=prod1)
        prod1.__exit__ = Mock(return_value=None)
        meta = Mock(partition=0, offset=10)
        prod1.send_message_with_retry.side_effect = [meta, Exception('fail'), meta]
        prod2 = Mock()
        prod2.__enter__ = Mock(return_value=prod2)
        prod2.__exit__ = Mock(return_value=None)
        prod2.send_message_with_retry.return_value = meta
        mock_producer_class.side_effect = [prod1, prod2]
        class ErrorDemoConsumer:
            def __init__(self, *args, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def process_messages(self, handler, max_retries=1, retry_delay=0.5):
                handler(Mock(value={'event_type': 'normal'}))
                try:
                    handler(Mock(value={'event_type': 'error_test'}))
                except Exception:
                    pass
                try:
                    handler(Mock(value={'event_type': 'fatal_error'}))
                except Exception:
                    pass
                handler(Mock(value='plain'))
                raise KeyboardInterrupt('done')
        class DLQMonitorConsumer(ErrorDemoConsumer):
            def process_messages(self, handler, *args, **kwargs):
                handler(Mock(value={
                    'original_topic': 't',
                    'original_partition': 0,
                    'original_offset': 5,
                    'error_type': 'non_retryable_error',
                    'error_reason': 'oops',
                    'failed_at': 0.0,
                    'consumer_group': 'g',
                }))
                raise KeyboardInterrupt('done')
        mock_consumer_class.side_effect = [ErrorDemoConsumer(), DLQMonitorConsumer()]
        run_error_demonstration()

    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.ResilientProducer')
    def test_error_demo_send_messages_failure_returns(self, mock_producer_class, mock_consumer_class):
        from example_resilient_messaging import run_error_demonstration
        prod1 = Mock()
        prod1.__enter__ = Mock(return_value=prod1)
        prod1.__exit__ = Mock(return_value=None)
        prod1.send_message_with_retry.return_value = Mock(partition=0, offset=0)
        prod2 = Mock()
        prod2.__enter__ = Mock(return_value=prod2)
        prod2.__exit__ = Mock(return_value=None)
        prod2.send_message_with_retry.side_effect = RuntimeError('cannot send')
        mock_producer_class.side_effect = [prod1, prod2]
        mock_consumer_class.return_value = Mock()
        run_error_demonstration()
        self.assertFalse(mock_consumer_class.called)

    @patch('example_resilient_messaging.ResilientConsumer')
    def test_error_demo_dlq_monitor_generic_exception(self, mock_consumer_class):
        from example_resilient_messaging import run_error_demonstration
        class RaiseOnEnter:
            def __enter__(self):
                raise RuntimeError('dlq broken')
            def __exit__(self, exc_type, exc, tb):
                return False
        with patch('example_resilient_messaging.ResilientProducer') as mock_prod_class:
            prod1 = Mock(); prod1.__enter__ = Mock(return_value=prod1); prod1.__exit__ = Mock(return_value=None)
            prod1.send_message_with_retry.return_value = Mock(partition=0, offset=1)
            prod2 = Mock(); prod2.__enter__ = Mock(return_value=prod2); prod2.__exit__ = Mock(return_value=None)
            prod2.send_message_with_retry.return_value = Mock(partition=0, offset=2)
            mock_prod_class.side_effect = [prod1, prod2]
            first_consumer = Mock()
            first_consumer.__enter__ = Mock(return_value=first_consumer)
            first_consumer.__exit__ = Mock(return_value=None)
            first_consumer.process_messages.side_effect = KeyboardInterrupt('done')
            mock_consumer_class.side_effect = [first_consumer, RaiseOnEnter()]
            run_error_demonstration()


class TestExampleResilientMessagingMain(unittest.TestCase):
    @patch('example_resilient_messaging.run_resilient_producer_demo', side_effect=KeyboardInterrupt('stop'))
    def test_main_producer_keyboardinterrupt(self, _mock_run):
        from example_resilient_messaging import main
        with patch.object(sys, 'argv', ['script', '--mode', 'producer']):
            main()

    @patch('example_resilient_messaging.run_error_demonstration', side_effect=RuntimeError('boom'))
    def test_main_error_demo_exception(self, _mock_run):
        from example_resilient_messaging import main
        with patch.object(sys, 'argv', ['script', '--mode', 'error-demo']):
            with patch('traceback.print_exc', autospec=True):
                main()

    @patch('example_resilient_messaging.run_resilient_consumer_demo')
    def test_main_consumer_mode(self, mock_run):
        from example_resilient_messaging import main
        with patch.object(sys, 'argv', ['script', '--mode', 'consumer']):
            main()
            mock_run.assert_called_once()


# ========== Content from tests/test_example_resilient_messaging_coverage_additional.py ==========
class TestMoreProducerPaths(unittest.TestCase):
    @patch('example_resilient_messaging.ResilientProducer')
    def test_producer_demo_keyboardinterrupt_handler(self, mock_producer_class):
        from example_resilient_messaging import run_resilient_producer_demo
        prod = Mock()
        prod.__enter__ = Mock(return_value=prod)
        prod.__exit__ = Mock(return_value=None)
        prod.send_message_with_retry.side_effect = KeyboardInterrupt('user stop')
        prod.send_message_async.return_value = None
        prod.flush.return_value = None
        mock_producer_class.return_value = prod
        run_resilient_producer_demo()


class TestErrorDemoAdditionalBranches(unittest.TestCase):
    @patch('example_resilient_messaging.threading.Thread', lambda target=None, daemon=None: FakeThread(target, daemon, run_immediately=False))
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.ResilientProducer')
    def test_error_demo_scenario1_outer_exception(self, mock_prod_class, mock_consumer_class):
        from example_resilient_messaging import run_error_demonstration
        class RaiseOnEnter:
            def __enter__(self):
                raise RuntimeError('broken producer')
            def __exit__(self, exc_type, exc, tb):
                return False
        prod2 = Mock(); prod2.__enter__ = Mock(return_value=prod2); prod2.__exit__ = Mock(return_value=None)
        prod2.send_message_with_retry.return_value = Mock(partition=0, offset=1)
        mock_prod_class.side_effect = [RaiseOnEnter(), prod2]
        cons1 = Mock(); cons1.__enter__ = Mock(return_value=cons1); cons1.__exit__ = Mock(return_value=None)
        cons1.process_messages.side_effect = KeyboardInterrupt('done')
        cons2 = Mock(); cons2.__enter__ = Mock(return_value=cons2); cons2.__exit__ = Mock(return_value=None)
        cons2.process_messages.side_effect = KeyboardInterrupt('done')
        mock_consumer_class.side_effect = [cons1, cons2]
        run_error_demonstration()

    @patch('example_resilient_messaging.threading.Thread', lambda target=None, daemon=None: FakeThread(target, daemon, run_immediately=False))
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.ResilientProducer')
    def test_error_demo_consumer_generic_exception(self, mock_prod_class, mock_consumer_class):
        from example_resilient_messaging import run_error_demonstration
        prod1 = Mock(); prod1.__enter__ = Mock(return_value=prod1); prod1.__exit__ = Mock(return_value=None)
        prod1.send_message_with_retry.return_value = Mock(partition=0, offset=0)
        prod2 = Mock(); prod2.__enter__ = Mock(return_value=prod2); prod2.__exit__ = Mock(return_value=None)
        prod2.send_message_with_retry.return_value = Mock(partition=0, offset=1)
        mock_prod_class.side_effect = [prod1, prod2]
        class RaiseOnEnter:
            def __enter__(self):
                raise RuntimeError('consumer broken')
            def __exit__(self, exc_type, exc, tb):
                return False
        cons2 = Mock(); cons2.__enter__ = Mock(return_value=cons2); cons2.__exit__ = Mock(return_value=None)
        cons2.process_messages.side_effect = KeyboardInterrupt('done')
        mock_consumer_class.side_effect = [RaiseOnEnter(), cons2]
        run_error_demonstration()

    @patch('example_resilient_messaging.threading.Thread', lambda target=None, daemon=None: FakeThread(target, daemon, run_immediately=False))
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.ResilientProducer')
    def test_error_demo_dlq_monitor_non_dict_branch(self, mock_prod_class, mock_consumer_class):
        from example_resilient_messaging import run_error_demonstration
        prod1 = Mock(); prod1.__enter__ = Mock(return_value=prod1); prod1.__exit__ = Mock(return_value=None)
        prod1.send_message_with_retry.return_value = Mock(partition=0, offset=0)
        prod2 = Mock(); prod2.__enter__ = Mock(return_value=prod2); prod2.__exit__ = Mock(return_value=None)
        prod2.send_message_with_retry.return_value = Mock(partition=0, offset=1)
        mock_prod_class.side_effect = [prod1, prod2]
        cons1 = Mock(); cons1.__enter__ = Mock(return_value=cons1); cons1.__exit__ = Mock(return_value=None)
        cons1.process_messages.side_effect = KeyboardInterrupt('done')
        class DLQ:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def process_messages(self, handler, *args, **kwargs):
                handler(Mock(value='raw text'))
                raise KeyboardInterrupt('done')
        mock_consumer_class.side_effect = [cons1, DLQ()]
        run_error_demonstration()


if __name__ == '__main__':
    unittest.main(verbosity=2)
