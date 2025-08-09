import unittest
from unittest.mock import Mock, MagicMock, patch

from kafka.errors import KafkaError


class TestResilientProducerCoverageBoost(unittest.TestCase):
    @patch('resilient_producer.KafkaProducer')
    @patch('resilient_producer.get_logger')
    def test_send_message_retry_loop_final_raise(self, mock_logger, mock_kafka_producer):
        # Construct producer with retries = -1 to skip loop and hit final raise
        from resilient_producer import ResilientProducer
        producer = ResilientProducer('localhost:9092', retries=-1)
        with self.assertRaises(KafkaError) as ctx:
            producer.send_message_with_retry('t', {'a': 1})
        self.assertIn('Unexpected end of retry loop without result', str(ctx.exception))

    @patch('resilient_producer.ResilientProducer')
    @patch('time.time')
    @patch('os.environ')
    def test_producer_example_usage_exception_and_callback_paths(self, mock_environ, mock_time, mock_producer_class):
        # Arrange
        mock_environ.get.side_effect = lambda k, d: {
            'KAFKA_BOOTSTRAP_SERVERS': 'localhost:9092',
            'KAFKA_TOPIC': 'resilient-test-topic',
        }.get(k, d)
        mock_time.return_value = 1234567890.0

        from resilient_producer import example_usage

        mock_producer = Mock()
        mock_producer.__enter__ = Mock(return_value=mock_producer)
        mock_producer.__exit__ = Mock(return_value=None)
        mock_producer_class.return_value = mock_producer

        # First send raises to exercise except print, then succeed twice
        mock_metadata = Mock(partition=0, offset=1)
        mock_producer.send_message_with_retry.side_effect = [Exception('boom'), mock_metadata, mock_metadata]

        # Capture callback passed into async send and invoke both branches
        def send_async_side_effect(topic, message, callback=None, key=None):
            if callback:
                # Trigger error branch
                callback(Exception('async error'), None)
                # Trigger success branch
                callback(None, Mock(partition=1, offset=2))
            return None

        mock_producer.send_message_async.side_effect = send_async_side_effect

        # Act - should not raise
        example_usage()

        # Assert that we attempted to send all messages and async was called
        self.assertEqual(mock_producer.send_message_with_retry.call_count, 3)
        mock_producer.send_message_async.assert_called_once()


class TestResilientConsumerCoverageBoost(unittest.TestCase):
    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_batch_processing_keyboard_interrupt_process_remaining(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        from resilient_consumer import ResilientConsumer

        # Create two messages then raise KeyboardInterrupt during iteration
        msg1 = Mock(topic='t', partition=0, offset=1, key='k', value={'id': 1})
        msg2 = Mock(topic='t', partition=0, offset=2, key='k', value={'id': 2})

        def gen():
            yield msg1
            yield msg2
            raise KeyboardInterrupt('stop')

        consumer_inst = MagicMock()
        consumer_inst.__iter__.side_effect = gen
        mock_kafka_consumer.return_value = consumer_inst
        logger_mock = Mock()
        mock_logger.return_value = logger_mock

        c = ResilientConsumer('localhost:9092', ['t'], 'g', dlq_topic='dlq')
        # Patch _process_batch to verify it is called with the remaining batch
        c._process_batch = Mock()

        # Act
        c.process_messages_batch(batch_handler=lambda b: None, batch_size=10, batch_timeout=100.0)

        # Assert leftover batch was processed once with two messages
        c._process_batch.assert_called_once()
        args, kwargs = c._process_batch.call_args
        self.assertEqual(len(args[0]), 2)
        # And graceful shutdown was logged
        logger_mock.info.assert_any_call("Shutting down gracefully...")

    @patch('resilient_consumer.time.sleep')
    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_process_batch_retry_exhausted_calls_handle_failed_batch(self, mock_logger, mock_kafka_consumer, mock_kafka_producer, mock_sleep):
        from resilient_consumer import ResilientConsumer, RetryableException
        mock_kafka_consumer.return_value = MagicMock(__iter__=MagicMock(return_value=iter([])))
        mock_logger.return_value = Mock()
        c = ResilientConsumer('localhost:9092', ['t'], 'g', dlq_topic='dlq')
        c._handle_failed_batch = Mock()

        def batch_handler(_batch):
            raise RetryableException('retry plz')

        batch = [Mock(topic='t', partition=0, offset=1, key='k', value='v')]
        c._process_batch(batch, batch_handler=batch_handler, max_retries=1)
        c._handle_failed_batch.assert_called_once()
        args, _ = c._handle_failed_batch.call_args
        self.assertEqual(args[1], 'retry plz')
        self.assertEqual(args[2], 'batch_max_retries_exceeded')

    @patch('resilient_consumer.KafkaProducer')
    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_process_batch_non_retryable_calls_handle_failed_batch(self, mock_logger, mock_kafka_consumer, mock_kafka_producer):
        from resilient_consumer import ResilientConsumer
        mock_kafka_consumer.return_value = MagicMock(__iter__=MagicMock(return_value=iter([])))
        mock_logger.return_value = Mock()
        c = ResilientConsumer('localhost:9092', ['t'], 'g', dlq_topic='dlq')
        c._handle_failed_batch = Mock()

        def batch_handler(_batch):
            raise ValueError('bad')

        batch = [Mock(topic='t', partition=0, offset=1, key='k', value='v')]
        c._process_batch(batch, batch_handler=batch_handler, max_retries=1)
        c._handle_failed_batch.assert_called_once()
        args, _ = c._handle_failed_batch.call_args
        self.assertEqual(args[1], 'bad')
        self.assertEqual(args[2], 'batch_non_retryable_error')

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_process_messages_batch_unexpected_exception_handling(self, mock_logger, mock_kafka_consumer):
        from resilient_consumer import ResilientConsumer
        # Make iteration raise a generic error to hit the generic except block
        consumer_inst = MagicMock()
        consumer_inst.__iter__.side_effect = RuntimeError('explode')
        mock_kafka_consumer.return_value = consumer_inst
        mock_logger.return_value = Mock()
        c = ResilientConsumer('localhost:9092', ['t'], 'g')
        with self.assertRaises(RuntimeError):
            c.process_messages_batch(batch_handler=lambda b: None)

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_get_current_offsets_mixed_none_and_values(self, mock_logger, mock_kafka_consumer):
        from resilient_consumer import ResilientConsumer
        from kafka import TopicPartition
        mock_logger.return_value = Mock()
        consumer_inst = MagicMock()
        tp1 = TopicPartition('t', 0)
        tp2 = TopicPartition('t', 1)
        consumer_inst.assignment.return_value = [tp1, tp2]
        # committed returns None for tp1 and a value for tp2
        offset_metadata = Mock()
        consumer_inst.committed.side_effect = [None, offset_metadata]
        mock_kafka_consumer.return_value = consumer_inst
        c = ResilientConsumer('localhost:9092', ['t'], 'g')
        result = c.get_current_offsets()
        self.assertNotIn(tp1, result)
        self.assertIn(tp2, result)
        self.assertIs(result[tp2], offset_metadata)

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_close_consumer_only(self, mock_logger, mock_kafka_consumer):
        from resilient_consumer import ResilientConsumer
        mock_logger.return_value = Mock()
        consumer_inst = MagicMock()
        mock_kafka_consumer.return_value = consumer_inst
        c = ResilientConsumer('localhost:9092', ['t'], 'g')  # no DLQ
        c.close()
        consumer_inst.close.assert_called_once()

    @patch('resilient_consumer.KafkaConsumer')
    @patch('resilient_consumer.get_logger')
    def test_close_when_both_none(self, mock_logger, mock_kafka_consumer):
        from resilient_consumer import ResilientConsumer
        mock_logger.return_value = Mock()
        consumer_inst = MagicMock()
        mock_kafka_consumer.return_value = consumer_inst
        c = ResilientConsumer('localhost:9092', ['t'], 'g')
        c.consumer = None
        c.dlq_producer = None
        # Should not raise
        c.close()

    @patch('resilient_consumer.ResilientConsumer')
    @patch('os.environ')
    def test_consumer_example_usage_handlers_execution(self, mock_environ, mock_consumer_class):
        # Arrange
        mock_environ.get.side_effect = lambda k, d: {
            'KAFKA_BOOTSTRAP_SERVERS': 'localhost:9092',
            'KAFKA_TOPIC': 'resilient-test-topic',
            'KAFKA_DLQ_TOPIC': 'resilient-test-topic-dlq',
        }.get(k, d)

        # Build a stub that executes the provided handlers to cover inner functions
        class StubConsumer:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def process_messages(self, handler, max_retries=2, retry_delay=0.5):
                # Call handler with different message shapes to exercise branches
                msg_text = Mock(key='k', value='hello')
                handler(msg_text)
                # Dict that succeeds
                msg_ok = Mock(key='k', value={'event_type': 'user_created'})
                handler(msg_ok)
                # Dict that raises RetryableException and ValueError; catch to avoid stopping example
                from resilient_consumer import RetryableException
                try:
                    msg_retry = Mock(key='k', value={'event_type': 'error_test'})
                    handler(msg_retry)
                except RetryableException:
                    pass
                try:
                    msg_fatal = Mock(key='k', value={'event_type': 'fatal_error'})
                    handler(msg_fatal)
                except ValueError:
                    pass
                # Exit example block
                raise KeyboardInterrupt('stop')
            def process_messages_batch(self, batch_handler, batch_size=5, batch_timeout=3.0):
                # First a successful batch to exercise success print
                messages_ok = [
                    Mock(key='k', value={'event_type': 'ok1'}),
                    Mock(key='k', value={'event_type': 'ok2'}),
                ]
                batch_handler(messages_ok)
                # Then a batch that triggers RetryableException in example handler
                messages_err = [
                    Mock(key='k', value={'event_type': 'batch_error'}),
                ]
                try:
                    batch_handler(messages_err)
                except Exception:
                    pass
                raise KeyboardInterrupt('stop')
        mock_consumer_class.return_value = StubConsumer()

        # Act
        from resilient_consumer import example_usage
        example_usage()


if __name__ == '__main__':
    unittest.main()
