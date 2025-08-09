"""
Unit tests for resilient Kafka messaging patterns.

This module tests:
1. ResilientProducer error handling and retry mechanisms
2. ResilientConsumer error handling and DLQ functionality
3. RetryableException behavior
4. Error scenarios and recovery patterns
"""

import os
# Import the modules to test
import sys
import unittest
from unittest.mock import Mock, patch, call

from kafka import TopicPartition
from kafka.errors import KafkaTimeoutError, KafkaError, RequestTimedOutError

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from resilient_producer import ResilientProducer
from resilient_consumer import ResilientConsumer, RetryableException, _safe_deserialize


class TestResilientProducer(unittest.TestCase):
    """Test cases for ResilientProducer."""

    def setUp(self):
        """Set up test fixtures."""
        self.bootstrap_servers = "localhost:9092"
        self.test_topic = "test-topic"
        self.test_message = {"id": 1, "data": "test message"}
        self.test_key = "test-key"

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_init_creates_producer_with_correct_config(self, mock_logger, mock_kafka_producer):
        """Test that ResilientProducer initializes with the correct configuration."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        producer = ResilientProducer(self.bootstrap_servers, retries=5, retry_delay=2.0)

        # Verify KafkaProducer was called with the correct configuration
        mock_kafka_producer.assert_called_once()
        call_args = mock_kafka_producer.call_args[1]

        self.assertEqual(call_args['bootstrap_servers'], self.bootstrap_servers)
        self.assertEqual(call_args['retries'], 5)
        self.assertEqual(call_args['max_in_flight_requests_per_connection'], 1)
        self.assertTrue(call_args['enable_idempotence'])
        self.assertEqual(call_args['acks'], 'all')

        # Verify logger was set up
        mock_logger.assert_called_with("resilient_producer")
        mock_logger_instance.info.assert_called_with("ResilientProducer initialized with reliability settings")

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_send_message_success(self, mock_logger, mock_kafka_producer):
        """Test a successful message sending."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger.return_value = Mock()

        mock_future = Mock()
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_future.get.return_value = mock_metadata
        mock_producer_instance.send.return_value = mock_future

        # Test
        producer = ResilientProducer(self.bootstrap_servers)
        result = producer.send_message_with_retry(self.test_topic, self.test_message, self.test_key)

        # Assertions
        mock_producer_instance.send.assert_called_once_with(
            self.test_topic, value=self.test_message, key=self.test_key
        )
        mock_future.get.assert_called_once_with(timeout=10)
        self.assertEqual(result, mock_metadata)

    @patch('resilient_producer.time.sleep')
    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_send_message_retry_on_timeout(self, mock_logger, mock_kafka_producer, mock_sleep):
        """Test retry logic on timeout error."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        mock_future = Mock()
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123

        # The first call raises timeout, the second succeeds
        mock_future.get.side_effect = [KafkaTimeoutError("Timeout"), mock_metadata]
        mock_producer_instance.send.return_value = mock_future

        # Test
        producer = ResilientProducer(self.bootstrap_servers, retries=2, retry_delay=1.0)
        result = producer.send_message_with_retry(self.test_topic, self.test_message)

        # Assertions
        self.assertEqual(mock_producer_instance.send.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)  # exponential backoff: 1.0 * (2^0)
        self.assertEqual(result, mock_metadata)

        # Verify warning was logged
        mock_logger_instance.warning.assert_called()

    @patch('resilient_producer.time.sleep')
    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_send_message_max_retries_exceeded(self, mock_logger, mock_kafka_producer, mock_sleep):
        """Test behavior when max retries are exceeded."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        mock_future = Mock()
        mock_future.get.side_effect = RequestTimedOutError("Timeout")
        mock_producer_instance.send.return_value = mock_future

        # Test
        producer = ResilientProducer(self.bootstrap_servers, retries=2, retry_delay=0.5)

        with self.assertRaises(RequestTimedOutError):
            producer.send_message_with_retry(self.test_topic, self.test_message)

        # Verify retries were attempted
        self.assertEqual(mock_producer_instance.send.call_count, 3)  # initial + 2 retries
        self.assertEqual(mock_sleep.call_count, 2)  # 2 retry delays

        # Verify exponential backoff
        expected_calls = [call(0.5), call(1.0)]  # 0.5 * 2^0, 0.5 * 2^1
        mock_sleep.assert_has_calls(expected_calls)

        # Verify error was logged
        mock_logger_instance.error.assert_called()

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_send_message_non_retriable_error(self, mock_logger, mock_kafka_producer):
        """Test immediate failure on non-retriable error."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        mock_future = Mock()
        # Use an error that's not in RETRIABLE_ERRORS
        non_retriable_error = KafkaError("Non-retriable error")
        mock_future.get.side_effect = non_retriable_error
        mock_producer_instance.send.return_value = mock_future

        # Test
        producer = ResilientProducer(self.bootstrap_servers, retries=2)

        with self.assertRaises(KafkaError):
            producer.send_message_with_retry(self.test_topic, self.test_message)

        # Verify no retries were attempted (only called once)
        self.assertEqual(mock_producer_instance.send.call_count, 1)

        # Verify error was logged
        mock_logger_instance.error.assert_called()

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_send_message_async_success(self, mock_logger, mock_kafka_producer):
        """Test async message sending with callback."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger.return_value = Mock()

        mock_future = Mock()
        mock_producer_instance.send.return_value = mock_future

        # Test
        producer = ResilientProducer(self.bootstrap_servers)
        callback = Mock()

        result = producer.send_message_async(self.test_topic, self.test_message, callback=callback)

        # Assertions
        mock_producer_instance.send.assert_called_once_with(
            self.test_topic, value=self.test_message, key=None
        )
        self.assertEqual(result, mock_future)

        # Verify callbacks were added to future
        mock_future.add_callback.assert_called_once()
        mock_future.add_errback.assert_called_once()

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_context_manager(self, mock_logger, mock_kafka_producer):
        """Test context manager functionality."""
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Test context manager
        with ResilientProducer(self.bootstrap_servers) as producer:
            self.assertIsInstance(producer, ResilientProducer)
        
        # Verify close was called
        mock_producer_instance.close.assert_called_once()
        mock_logger_instance.info.assert_any_call("Closing resilient producer...")

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_send_message_unexpected_exception(self, mock_logger, mock_kafka_producer):
        """Test handling of unexpected exceptions during send."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        mock_future = Mock()
        # Simulate unexpected exception (not a Kafka error)
        mock_future.get.side_effect = ValueError("Unexpected error")
        mock_producer_instance.send.return_value = mock_future
        
        # Test
        producer = ResilientProducer(self.bootstrap_servers, retries=1)
        
        with self.assertRaises(KafkaError) as context:
            producer.send_message_with_retry(self.test_topic, self.test_message)
        
        # Verify the unexpected error was wrapped in KafkaError
        self.assertIn("Unexpected error", str(context.exception))
        
        # Verify error was logged
        mock_logger_instance.error.assert_called()
        error_call_args = mock_logger_instance.error.call_args[0][0]
        self.assertIn("Unexpected error while sending message", error_call_args)

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_send_message_retry_loop_fallback(self, mock_logger, mock_kafka_producer):
        """Test the fallback error at end of retry loop."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock send to return a future that never completes normally
        # This is a edge case that should theoretically never happen
        mock_future = Mock()
        mock_producer_instance.send.return_value = mock_future
        
        # Mock future.get to return None (no exception, no metadata)
        mock_future.get.return_value = None
        
        # Test
        producer = ResilientProducer(self.bootstrap_servers, retries=1)
        
        # This should trigger an AttributeError internally, which gets wrapped in KafkaError
        with self.assertRaises(KafkaError):
            # The real implementation tries to access .partition on None, which raises AttributeError
            # but gets caught and wrapped in KafkaError as designed
            producer.send_message_with_retry(self.test_topic, self.test_message)

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_async_send_exception_handling(self, mock_logger, mock_kafka_producer):
        """Test exception handling in async send method."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock producer.send to raise exception
        mock_producer_instance.send.side_effect = Exception("Async send error")
        
        # Test with callback
        callback = Mock()
        producer = ResilientProducer(self.bootstrap_servers)
        
        with self.assertRaises(Exception) as context:
            producer.send_message_async(self.test_topic, self.test_message, callback=callback)
        
        self.assertEqual(str(context.exception), "Async send error")
        
        # Verify callback was called with error
        callback.assert_called_once_with(context.exception, None)
        
        # Verify error was logged
        mock_logger_instance.error.assert_called()
        error_call_args = mock_logger_instance.error.call_args[0][0]
        self.assertIn("Error in async send", error_call_args)

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_async_send_without_callback(self, mock_logger, mock_kafka_producer):
        """Test async send without callback handles exceptions."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock producer.send to raise exception
        mock_producer_instance.send.side_effect = Exception("Async send error")
        
        # Test without callback
        producer = ResilientProducer(self.bootstrap_servers)
        
        with self.assertRaises(Exception) as context:
            producer.send_message_async(self.test_topic, self.test_message)
        
        self.assertEqual(str(context.exception), "Async send error")
        
        # Verify error was logged
        mock_logger_instance.error.assert_called()

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_flush_method_success(self, mock_logger, mock_kafka_producer):
        """Test successful flush operation."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Test
        producer = ResilientProducer(self.bootstrap_servers)
        producer.flush(timeout=10)
        
        # Verify flush was called with timeout
        mock_producer_instance.flush.assert_called_once_with(timeout=10)
        
        # Verify logging
        mock_logger_instance.debug.assert_called_with("Flushing producer buffer...")
        mock_logger_instance.info.assert_called_with("Producer buffer flushed successfully")

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_flush_method_error(self, mock_logger, mock_kafka_producer):
        """Test flush method error handling."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock flush to raise exception
        flush_error = Exception("Flush failed")
        mock_producer_instance.flush.side_effect = flush_error
        
        # Test
        producer = ResilientProducer(self.bootstrap_servers)
        
        with self.assertRaises(Exception) as context:
            producer.flush()
        
        self.assertEqual(context.exception, flush_error)
        
        # Verify error was logged
        mock_logger_instance.error.assert_called()
        error_call_args = mock_logger_instance.error.call_args[0][0]
        self.assertIn("Error flushing producer", error_call_args)

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_close_method_success(self, mock_logger, mock_kafka_producer):
        """Test successful close operation."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Test
        producer = ResilientProducer(self.bootstrap_servers)
        producer.close(timeout=5)
        
        # Verify close was called with timeout
        mock_producer_instance.close.assert_called_once_with(timeout=5)
        
        # Verify logging
        mock_logger_instance.info.assert_any_call("Closing resilient producer...")
        mock_logger_instance.info.assert_any_call("Resilient producer closed successfully")

    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_close_method_error(self, mock_logger, mock_kafka_producer):
        """Test close method error handling."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock close to raise exception
        close_error = Exception("Close failed")
        mock_producer_instance.close.side_effect = close_error
        
        # Test
        producer = ResilientProducer(self.bootstrap_servers)
        
        with self.assertRaises(Exception) as context:
            producer.close()
        
        self.assertEqual(context.exception, close_error)
        
        # Verify error was logged
        mock_logger_instance.error.assert_called()
        error_call_args = mock_logger_instance.error.call_args[0][0]
        self.assertIn("Error closing producer", error_call_args)


class TestResilientConsumer(unittest.TestCase):
    """Test cases for ResilientConsumer."""

    def setUp(self):
        """Set up test fixtures."""
        self.bootstrap_servers = "localhost:9092"
        self.test_topics = ["test-topic"]
        self.group_id = "test-group"
        self.dlq_topic = "test-dlq"

    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_init_creates_consumer_with_dlq(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        """Test ResilientConsumer initialization with DLQ."""
        mock_logger.return_value = Mock()

        consumer = ResilientConsumer(
            self.bootstrap_servers,
            self.test_topics,
            self.group_id,
            self.dlq_topic
        )

        # Verify KafkaConsumer was created with the correct config
        mock_kafka_consumer.assert_called_once()
        consumer_args = mock_kafka_consumer.call_args[1]

        self.assertEqual(consumer_args['bootstrap_servers'], self.bootstrap_servers)
        self.assertEqual(consumer_args['group_id'], self.group_id)
        self.assertFalse(consumer_args['enable_auto_commit'])
        self.assertEqual(consumer_args['max_poll_records'], 10)

        # Verify DLQ producer was created
        mock_kafka_producer.assert_called_once()

        self.assertEqual(consumer.topics, self.test_topics)
        self.assertEqual(consumer.group_id, self.group_id)
        self.assertEqual(consumer.dlq_topic, self.dlq_topic)

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_init_without_dlq(self, mock_logger, mock_kafka_consumer):
        """Test ResilientConsumer initialization without DLQ."""
        mock_logger.return_value = Mock()

        consumer = ResilientConsumer(
            self.bootstrap_servers,
            self.test_topics,
            self.group_id
        )

        # Verify no DLQ producer was created
        self.assertIsNone(consumer.dlq_producer)
        self.assertIsNone(consumer.dlq_topic)

    def test_safe_deserialize_json(self):
        """Test safe JSON deserialization."""
        # Setup
        consumer = ResilientConsumer  # Create an instance without __init__

        # Test valid JSON
        json_data = b'{"key": "value"}'
        result = _safe_deserialize(json_data)
        self.assertEqual(result, {"key": "value"})

        # Test invalid JSON
        invalid_json = b'invalid json'
        result = _safe_deserialize(invalid_json)
        self.assertEqual(result, "invalid json")

        # Test non-UTF8 bytes
        non_utf8 = b'\x80\x81\x82'
        result = _safe_deserialize(non_utf8)
        self.assertIsInstance(result, str)  # Should not raise exception

    @patch('resilient_consumer.time.sleep')
    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_process_message_with_retry(self, mock_logger, mock_kafka_consumer, mock_kafka_producer, mock_sleep):
        """Test message processing with retry logic."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Create a mock message
        mock_message = Mock()
        mock_message.topic = "test-topic"
        mock_message.partition = 0
        mock_message.offset = 123
        mock_message.key = "test-key"
        mock_message.value = {"id": 1, "data": "test"}

        # Mock consumer to return one message then stop
        mock_consumer_instance.__iter__ = Mock(return_value=iter([mock_message]))

        # Test handler that fails once then succeeds
        call_count = [0]

        def test_handler(message):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RetryableException("Test error")
            # Success on the second call

        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)

        # Mock the close method to stop iteration
        def mock_close():
            raise KeyboardInterrupt("Test stop")

        consumer.close = mock_close

        with self.assertRaises(KeyboardInterrupt):
            consumer.process_messages(test_handler, max_retries=2, retry_delay=0.1)

        # Verify handler was called twice (initial + 1 retry)
        self.assertEqual(call_count[0], 2)

        # Verify sleep was called for retry
        mock_sleep.assert_called_once_with(0.1)

        # Verify commit was called after success
        mock_consumer_instance.commit.assert_called()

    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_send_to_dlq(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        """Test sending a message to the dead letter queue."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger.return_value = Mock()

        mock_future = Mock()
        mock_producer_instance.send.return_value = mock_future

        # Create a mock original message
        mock_message = Mock()
        mock_message.topic = "original-topic"
        mock_message.partition = 1
        mock_message.offset = 456
        mock_message.key = "msg-key"
        mock_message.value = {"id": 1, "data": "failed message"}
        mock_message.timestamp = 1234567890

        # Test
        consumer = ResilientConsumer(
            self.bootstrap_servers,
            self.test_topics,
            self.group_id,
            self.dlq_topic
        )

        consumer._send_to_dlq(mock_message, "Test error", "test_error_type")

        # Verify DLQ message was sent
        mock_producer_instance.send.assert_called_once()
        call_args = mock_producer_instance.send.call_args

        self.assertEqual(call_args[1]['key'], "msg-key")

        dlq_message = call_args[1]['value']
        self.assertEqual(dlq_message['original_topic'], "original-topic")
        self.assertEqual(dlq_message['original_partition'], 1)
        self.assertEqual(dlq_message['original_offset'], 456)
        self.assertEqual(dlq_message['error_reason'], "Test error")
        self.assertEqual(dlq_message['error_type'], "test_error_type")
        self.assertEqual(dlq_message['consumer_group'], self.group_id)

        # Verify future.get was called to wait for confirmation
        mock_future.get.assert_called_once_with(timeout=5)

    @patch('resilient_consumer.time.sleep')
    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_batch_processing_with_retry(self, mock_logger, mock_kafka_consumer, mock_kafka_producer, mock_sleep):
        """Test batch processing with retry logic."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        # Create mock messages for batch
        messages = []
        for i in range(3):
            msg = Mock()
            msg.topic = "test-topic"
            msg.partition = 0
            msg.offset = 100 + i
            msg.value = {"id": i, "data": f"message {i}"}
            messages.append(msg)

        # Mock consumer to return messages then stop
        mock_consumer_instance.__iter__ = Mock(return_value=iter(messages))

        # Test batch handler that fails once then succeeds
        call_count = [0]

        def batch_handler(batch):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RetryableException("Batch processing error")
            # Success on the second call

        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)

        # Mock the close method to stop after processing
        def mock_close():
            raise KeyboardInterrupt("Test stop")

        consumer.close = mock_close

        with self.assertRaises(KeyboardInterrupt):
            consumer.process_messages_batch(
                batch_handler,
                batch_size=2,  # Smaller than the number of messages (3) to trigger processing
                batch_timeout=1.0,
                max_retries=2
            )

        # Verify batch handler was called twice (initial + 1 retry)
        self.assertEqual(call_count[0], 2)

        # Verify sleep was called for retry (exponential backoff: 1.0 * 2^0)
        mock_sleep.assert_called_once_with(1.0)

        # Verify commit was called after success
        mock_consumer_instance.commit.assert_called()

    @patch('resilient_consumer.time.sleep')
    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_process_message_max_retries_exceeded(self, mock_logger, mock_kafka_consumer, mock_kafka_producer, mock_sleep):
        """Test max retries exceeded scenario with DLQ."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Create mock message
        mock_message = Mock()
        mock_message.topic = "test-topic"
        mock_message.partition = 0
        mock_message.offset = 123
        mock_message.key = "test-key"
        mock_message.value = {"id": 1, "data": "test"}
        
        # Mock consumer to return one message then stop
        mock_consumer_instance.__iter__ = Mock(return_value=iter([mock_message]))
        
        # Test handler that always fails with retriable exception
        def failing_handler(message):
            raise RetryableException("Always fails")
        
        # Mock the close method to stop iteration after processing
        def mock_close():
            raise KeyboardInterrupt("Test stop")
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id, self.dlq_topic)
        consumer.close = mock_close
        
        with self.assertRaises(KeyboardInterrupt):
            consumer.process_messages(failing_handler, max_retries=2, retry_delay=0.1)
        
        # Verify handler was called 3 times (initial + 2 retries)
        # We can't directly verify call count, but we can check sleep calls
        self.assertEqual(mock_sleep.call_count, 2)  # 2 retry delays
        
        # Verify DLQ message was sent after max retries
        mock_producer_instance.send.assert_called_once()
        
        # Verify commit was called to skip the failed message
        mock_consumer_instance.commit.assert_called()
        
        # Verify error logging
        mock_logger_instance.error.assert_called()

    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_process_message_keyboard_interrupt(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        """Test graceful shutdown on KeyboardInterrupt."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock consumer to raise KeyboardInterrupt immediately
        mock_consumer_instance.__iter__ = Mock(side_effect=KeyboardInterrupt("User interrupt"))
        
        # Test handler (won't be called)
        def test_handler(message):
            pass
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        consumer.process_messages(test_handler)
        
        # Verify graceful shutdown message was logged
        mock_logger_instance.info.assert_any_call("Shutting down gracefully...")

    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_process_message_unexpected_exception(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        """Test handling of unexpected exceptions during message processing."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock consumer to raise unexpected exception
        mock_consumer_instance.__iter__ = Mock(side_effect=Exception("Unexpected error"))
        
        # Test handler (won't be called)
        def test_handler(message):
            pass
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        
        with self.assertRaises(Exception) as context:
            consumer.process_messages(test_handler)
        
        self.assertEqual(str(context.exception), "Unexpected error")
        
        # Verify error was logged
        mock_logger_instance.error.assert_called()
        error_call_args = mock_logger_instance.error.call_args[0][0]
        self.assertIn("Unexpected error in message processing", error_call_args)

    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_dlq_producer_failure(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        """Test DLQ producer failure handling."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Create mock message
        mock_message = Mock()
        mock_message.topic = "test-topic"
        mock_message.partition = 0
        mock_message.offset = 123
        mock_message.key = "test-key"
        mock_message.value = {"id": 1, "data": "test"}
        
        # Mock consumer to return one message
        mock_consumer_instance.__iter__ = Mock(return_value=iter([mock_message]))
        
        # Mock DLQ producer to fail
        mock_future = Mock()
        mock_future.get.side_effect = Exception("DLQ send failed")
        mock_producer_instance.send.return_value = mock_future
        
        # Test handler that fails
        def failing_handler(message):
            raise ValueError("Non-retriable error")
        
        # Mock close to stop after processing
        def mock_close():
            raise KeyboardInterrupt("Test stop")
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id, self.dlq_topic)
        consumer.close = mock_close
        
        with self.assertRaises(KeyboardInterrupt):
            consumer.process_messages(failing_handler)
        
        # Verify DLQ send was attempted
        mock_producer_instance.send.assert_called()
        
        # Verify DLQ failure was logged
        mock_logger_instance.error.assert_called()
        # Check for DLQ error message in the log calls
        error_calls = [call[0][0] for call in mock_logger_instance.error.call_args_list]
        dlq_error_logged = any("Failed to send message to DLQ" in call for call in error_calls)
        self.assertTrue(dlq_error_logged)

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_dlq_not_configured_warning(self, mock_logger, mock_kafka_consumer):
        """Test warning when DLQ is not configured."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Create mock message
        mock_message = Mock()
        mock_message.topic = "test-topic"
        mock_message.partition = 0
        mock_message.offset = 123
        mock_message.key = "test-key"
        mock_message.value = {"id": 1, "data": "test"}
        
        # Test without DLQ topic
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        
        # Call _send_to_dlq directly to test warning
        consumer._send_to_dlq(mock_message, "Test error", "test_error_type")
        
        # Verify warning was logged
        mock_logger_instance.warning.assert_called()
        warning_call_args = mock_logger_instance.warning.call_args[0][0]
        self.assertIn("No DLQ configured - dropping failed message", warning_call_args)

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_commit_sync_success(self, mock_logger, mock_kafka_consumer):
        """Test successful synchronous commit."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        consumer.commit_sync()
        
        # Verify commit was called
        mock_consumer_instance.commit.assert_called_once()
        
        # Verify success was logged
        mock_logger_instance.debug.assert_called_with("Offsets committed successfully")

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_commit_sync_failure(self, mock_logger, mock_kafka_consumer):
        """Test commit sync failure handling."""
        from kafka.errors import CommitFailedError
        
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock commit to raise CommitFailedError
        commit_error = CommitFailedError("Commit failed")
        mock_consumer_instance.commit.side_effect = commit_error
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        
        with self.assertRaises(CommitFailedError) as context:
            consumer.commit_sync()
        
        self.assertEqual(context.exception, commit_error)
        
        # Verify error was logged
        mock_logger_instance.error.assert_called()
        error_call_args = mock_logger_instance.error.call_args[0][0]
        self.assertIn("Failed to commit offsets", error_call_args)

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_seek_to_beginning_with_partitions(self, mock_logger, mock_kafka_consumer):
        """Test seek to beginning with specific partitions."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Create test partitions
        test_partitions = [TopicPartition('test-topic', 0), TopicPartition('test-topic', 1)]
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        consumer.seek_to_beginning(test_partitions)
        
        # Verify seek_to_beginning was called with partitions
        mock_consumer_instance.seek_to_beginning.assert_called_once_with(*test_partitions)
        
        # Verify info was logged
        mock_logger_instance.info.assert_called_with("Seeked to beginning of partitions")

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_seek_to_beginning_all_partitions(self, mock_logger, mock_kafka_consumer):
        """Test seek to beginning for all assigned partitions."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        consumer.seek_to_beginning()
        
        # Verify seek_to_beginning was called without arguments
        mock_consumer_instance.seek_to_beginning.assert_called_once()
        
        # Verify info was logged
        mock_logger_instance.info.assert_called_with("Seeked to beginning of partitions")

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_get_current_offsets_success(self, mock_logger, mock_kafka_consumer):
        """Test successful retrieval of current offsets."""
        from kafka.structs import OffsetAndMetadata
        
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Create test partitions and offset metadata
        test_partitions = {TopicPartition('test-topic', 0), TopicPartition('test-topic', 1)}
        offset_metadata = OffsetAndMetadata(100, "test-metadata", None)
        
        mock_consumer_instance.assignment.return_value = test_partitions
        mock_consumer_instance.committed.return_value = offset_metadata
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        result = consumer.get_current_offsets()
        
        # Verify assignment and committed were called
        mock_consumer_instance.assignment.assert_called_once()
        
        # Since we call committed() for each partition individually, verify it was called
        self.assertEqual(mock_consumer_instance.committed.call_count, len(test_partitions))
        
        # Verify result contains the expected partitions
        self.assertEqual(len(result), len(test_partitions))

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_get_current_offsets_failure(self, mock_logger, mock_kafka_consumer):
        """Test get current offsets failure handling."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock assignment to raise exception
        mock_consumer_instance.assignment.side_effect = Exception("Assignment failed")
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        result = consumer.get_current_offsets()
        
        # Verify empty dict is returned on error
        self.assertEqual(result, {})
        
        # Verify error was logged
        mock_logger_instance.error.assert_called()
        error_call_args = mock_logger_instance.error.call_args[0][0]
        self.assertIn("Failed to get current offsets", error_call_args)

    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_close_with_dlq_producer(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        """Test close method with DLQ producer cleanup."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id, self.dlq_topic)
        consumer.close()
        
        # Verify both consumer and DLQ producer were closed
        mock_consumer_instance.close.assert_called_once()
        mock_producer_instance.close.assert_called_once()
        
        # Verify logging
        mock_logger_instance.info.assert_any_call("Closing resilient consumer...")
        mock_logger_instance.info.assert_any_call("Resilient consumer closed successfully")

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_close_error_handling(self, mock_logger, mock_kafka_consumer):
        """Test close method error handling."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock close to raise exception
        mock_consumer_instance.close.side_effect = Exception("Close failed")
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        consumer.close()
        
        # Verify error was logged (but not raised)
        mock_logger_instance.error.assert_called()
        error_call_args = mock_logger_instance.error.call_args[0][0]
        self.assertIn("Error closing consumer", error_call_args)

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_context_manager_with_exception(self, mock_logger, mock_kafka_consumer):
        """Test context manager cleanup when exception occurs."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Test context manager with exception
        try:
            with ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id) as consumer:
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected
        
        # Verify close was called even with exception
        mock_consumer_instance.close.assert_called_once()


class TestRetryableException(unittest.TestCase):
    """Test cases for RetryableException."""

    def test_retryable_exception_creation(self):
        """Test RetryableException can be created and raised."""
        error_message = "This is a retriable error"

        with self.assertRaises(RetryableException) as context:
            raise RetryableException(error_message)

        self.assertEqual(str(context.exception), error_message)
        self.assertIsInstance(context.exception, Exception)


class TestErrorScenarios(unittest.TestCase):
    """Integration tests for various error scenarios."""

    @patch('resilient_producer.time.sleep')
    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_producer_retry_scenarios(self, mock_logger, mock_kafka_producer, mock_sleep):
        """Test different retry scenarios for producer."""
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger.return_value = Mock()

        # Test scenario: timeout -> success
        mock_future = Mock()
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 789

        mock_future.get.side_effect = [
            KafkaTimeoutError("First attempt timeout"),
            mock_metadata  # Second attempt success
        ]
        mock_producer_instance.send.return_value = mock_future

        producer = ResilientProducer("localhost:9092", retries=3, retry_delay=0.5)
        result = producer.send_message_with_retry("test-topic", {"test": "data"})

        # Verify success after retry
        self.assertEqual(result, mock_metadata)
        self.assertEqual(mock_producer_instance.send.call_count, 2)
        mock_sleep.assert_called_once_with(0.5)  # First retry delay

    @patch('resilient_consumer.time.sleep')
    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_consumer_dlq_scenarios(self, mock_logger, mock_kafka_consumer, mock_kafka_producer, mock_sleep):
        """Test DLQ scenarios for consumer."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger.return_value = Mock()

        # Create a mock message that will fail to process
        mock_message = Mock()
        mock_message.topic = "test-topic"
        mock_message.partition = 0
        mock_message.offset = 999
        mock_message.key = "failed-key"
        mock_message.value = {"id": 999, "type": "fail"}

        mock_consumer_instance.__iter__ = Mock(return_value=iter([mock_message]))

        # Handler that always fails with a non-retriable error
        def failing_handler(message):
            raise ValueError("Non-retriable processing error")

        consumer = ResilientConsumer(
            "localhost:9092",
            ["test-topic"],
            "test-group",
            "test-dlq"
        )

        # Mock close to stop after the first message
        def mock_close():
            raise KeyboardInterrupt("Test stop")

        consumer.close = mock_close

        with self.assertRaises(KeyboardInterrupt):
            consumer.process_messages(failing_handler, max_retries=2)

        # Verify message was sent to DLQ
        mock_producer_instance.send.assert_called_once()

        # Verify offset was committed (to skip the failed message)
        mock_consumer_instance.commit.assert_called()

        # Verify no sleep was called (non-retriable error, no retries)
        mock_sleep.assert_not_called()


class TestResilientProducerAdditionalCoverage(unittest.TestCase):
    """Additional tests to cover remaining lines in ResilientProducer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bootstrap_servers = "localhost:9092"
        self.test_topic = "test-topic"
        self.test_message = {"id": 1, "data": "test message"}
    
    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_async_send_without_callback_no_exception(self, mock_logger, mock_kafka_producer):
        """Test async send without callback when no exception occurs."""
        # Setup mocks
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        mock_future = Mock()
        mock_producer_instance.send.return_value = mock_future
        
        # Test without callback
        producer = ResilientProducer(self.bootstrap_servers)
        result = producer.send_message_async(self.test_topic, self.test_message)
        
        # Should return the future
        self.assertEqual(result, mock_future)
        
        # Verify no callbacks were added since no callback provided
        mock_future.add_callback.assert_not_called()
        mock_future.add_errback.assert_not_called()
        
        # Verify debug log was called
        mock_logger_instance.debug.assert_called_with(f"Async message sent to {self.test_topic}")
    
    @patch('os.environ')
    @patch('time.time')
    @patch('resilient_producer.ResilientProducer')
    def test_example_usage_function(self, mock_producer_class, mock_time, mock_environ):
        """Test the example_usage function for full coverage."""
        from resilient_producer import example_usage
        
        # Mock environment variables
        mock_environ.get.side_effect = lambda key, default: {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
            "KAFKA_TOPIC": "resilient-test-topic"
        }.get(key, default)
        
        # Mock time.time()
        mock_time.return_value = 1234567890.0
        
        # Mock producer instance and context manager
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer
        
        # Mock successful sends
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_producer.send_message_with_retry.return_value = mock_metadata
        
        # Call the example function
        example_usage()
        
        # Verify producer was initialized correctly
        mock_producer_class.assert_called_with("localhost:9092", retries=3, retry_delay=1.0)
        
        # Verify sync sends were called (3 messages)
        self.assertEqual(mock_producer.send_message_with_retry.call_count, 3)
        
        # Verify async send was called
        mock_producer.send_message_async.assert_called_once()
        
        # Verify flush was called
        mock_producer.flush.assert_called_once()


class TestResilientConsumerAdditionalCoverage(unittest.TestCase):
    """Additional tests to cover remaining lines in ResilientConsumer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bootstrap_servers = "localhost:9092"
        self.test_topics = ["test-topic"]
        self.group_id = "test-group"
        self.dlq_topic = "test-dlq"
    
    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_batch_processing_keyboard_interrupt_with_remaining_batch(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        """Test batch processing KeyboardInterrupt with remaining messages."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Create messages that will form an incomplete batch
        messages = [Mock(topic="test", partition=0, offset=i, value={"id": i}) for i in range(2)]
        
        # Mock consumer iterator that raises KeyboardInterrupt after yielding messages
        mock_consumer_instance.__iter__ = Mock(return_value=iter(messages + [KeyboardInterrupt("User interrupt")]))
        
        # Override the iterator behavior to raise KeyboardInterrupt
        def side_effect_iter():
            for msg in messages:
                yield msg
            raise KeyboardInterrupt("User interrupt")
        
        mock_consumer_instance.__iter__ = Mock(side_effect=side_effect_iter)
        
        # Mock successful batch processing
        batch_handler_calls = []
        def mock_batch_handler(batch):
            batch_handler_calls.append(len(batch))
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id)
        consumer.process_messages_batch(mock_batch_handler, batch_size=5, batch_timeout=1.0)
        
        # Verify the remaining batch was processed
        self.assertEqual(len(batch_handler_calls), 1)
        self.assertEqual(batch_handler_calls[0], 2)  # Both messages in final batch
        
        # Verify graceful shutdown or cleanup message was logged
        mock_logger_instance.info.assert_any_call("Shutting down gracefully...")
        # Alternative: check for resource cleanup message
        shutdown_calls = [call for call in mock_logger_instance.info.call_args_list 
                         if "gracefully" in str(call) or "closed successfully" in str(call)]
        self.assertGreater(len(shutdown_calls), 0)
    
    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_handle_failed_batch(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        """Test _handle_failed_batch method directly."""
        # Setup mocks
        mock_consumer_instance = Mock()
        mock_kafka_consumer.return_value = mock_consumer_instance
        mock_producer_instance = Mock()
        mock_kafka_producer.return_value = mock_producer_instance
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        
        # Create test batch
        batch = [
            Mock(topic="test", partition=0, offset=100, key="key1", value={"id": 1}),
            Mock(topic="test", partition=0, offset=101, key="key2", value={"id": 2})
        ]
        
        # Test
        consumer = ResilientConsumer(self.bootstrap_servers, self.test_topics, self.group_id, self.dlq_topic)
        consumer._handle_failed_batch(batch, "Test batch error", "batch_test_error")
        
        # Verify all messages were sent to DLQ
        self.assertEqual(mock_producer_instance.send.call_count, 2)
        
        # Verify commit was called to skip failed batch
        mock_consumer_instance.commit.assert_called_once()
        
        # Verify logging - check that both the batch handling and DLQ messages were logged
        mock_logger_instance.info.assert_any_call(f"Handling failed batch of {len(batch)} messages...")
        # Also verify DLQ messages were logged for each message in batch
        dlq_calls = [call for call in mock_logger_instance.info.call_args_list 
                    if 'Message sent to DLQ' in str(call)]
        self.assertEqual(len(dlq_calls), len(batch))
    
    @patch('os.environ')
    @patch('resilient_consumer.ResilientConsumer')
    def test_example_usage_function(self, mock_consumer_class, mock_environ):
        """Test the example_usage function for full coverage."""
        from resilient_consumer import example_usage
        
        # Mock environment variables
        mock_environ.get.side_effect = lambda key, default: {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
            "KAFKA_TOPIC": "resilient-test-topic", 
            "KAFKA_DLQ_TOPIC": "resilient-test-topic-dlq"
        }.get(key, default)
        
        # Mock consumer instances and context manager
        mock_consumer = Mock()
        mock_consumer.__enter__ = Mock(return_value=mock_consumer)
        mock_consumer.__exit__ = Mock(return_value=None)
        mock_consumer_class.return_value = mock_consumer
        
        # Mock KeyboardInterrupt to stop processing
        mock_consumer.process_messages.side_effect = KeyboardInterrupt("Test stop")
        mock_consumer.process_messages_batch.side_effect = KeyboardInterrupt("Test stop")
        
        # Call the example function
        example_usage()
        
        # Verify consumer was initialized for both examples (2 calls)
        self.assertEqual(mock_consumer_class.call_count, 2)
        
        # Verify both processing methods were called
        mock_consumer.process_messages.assert_called_once()
        mock_consumer.process_messages_batch.assert_called_once()


class TestExampleMessagingAdditionalCoverage(unittest.TestCase):
    """Additional tests to cover remaining lines in example_resilient_messaging.py."""
    
    @patch('example_resilient_messaging.ResilientProducer')
    def test_producer_demo_error_handling_paths(self, mock_producer_class):
        """Test error handling paths in producer demo."""
        from example_resilient_messaging import run_resilient_producer_demo
        
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer
        
        # Mock some sends to fail and some to succeed
        mock_metadata = Mock(partition=0, offset=123)
        mock_producer.send_message_with_retry.side_effect = [
            Exception("First send failed"),  # This will be caught and logged
            mock_metadata,  # This will succeed
            mock_metadata   # This will succeed
        ]
        
        # Mock async sends and flush
        mock_producer.send_message_async.return_value = None
        mock_producer.flush.return_value = None
        
        # Should complete without raising exception
        run_resilient_producer_demo()
        
        # Verify error was handled gracefully
        self.assertTrue(mock_producer.send_message_with_retry.called)
    
    @patch('example_resilient_messaging.threading.Thread')
    @patch('example_resilient_messaging.ResilientConsumer') 
    def test_consumer_demo_stats_thread(self, mock_consumer_class, mock_thread):
        """Test stats printing thread in consumer demo."""
        from example_resilient_messaging import run_resilient_consumer_demo
        
        mock_consumer = Mock()
        mock_consumer.__enter__ = Mock(return_value=mock_consumer)
        mock_consumer.__exit__ = Mock(return_value=None)
        mock_consumer_class.return_value = mock_consumer
        
        # Mock thread
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        # Mock process_messages to raise KeyboardInterrupt immediately
        mock_consumer.process_messages.side_effect = KeyboardInterrupt("Test stop")
        
        # Call consumer demo
        run_resilient_consumer_demo()
        
        # Verify stats thread was started
        mock_thread_instance.start.assert_called_once()
    
    @patch('example_resilient_messaging.threading.Thread')
    @patch('example_resilient_messaging.ResilientConsumer')
    @patch('example_resilient_messaging.ResilientProducer')
    def test_error_demo_complete_flow(self, mock_producer_class, mock_consumer_class, mock_thread):
        """Test complete error demonstration flow."""
        from example_resilient_messaging import run_error_demonstration
        
        # Setup producer mock
        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer
        
        mock_metadata = Mock(partition=0, offset=123)
        mock_producer.send_message_with_retry.return_value = mock_metadata
        
        # Setup consumer mock
        mock_consumer = Mock()
        mock_consumer.__enter__ = Mock(return_value=mock_consumer)
        mock_consumer.__exit__ = Mock(return_value=None)
        mock_consumer_class.return_value = mock_consumer
        
        # Mock consumer processing to stop quickly
        mock_consumer.process_messages.side_effect = KeyboardInterrupt("Demo timeout")
        
        # Mock thread for timer
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        # Call error demonstration
        run_error_demonstration()
        
        # Verify all three scenarios were attempted
        # Scenario 1: Producer error handling
        self.assertTrue(mock_producer.send_message_with_retry.called)
        
        # Scenario 2: Consumer error handling
        self.assertTrue(mock_consumer.process_messages.called)
        
        # Scenario 3: DLQ monitoring (second consumer instance)
        self.assertTrue(mock_consumer_class.call_count >= 2)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
