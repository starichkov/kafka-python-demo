"""
Resilient Kafka Producer with Error Handling and Retry Mechanisms

This module provides a robust Kafka producer implementation that extends the basic producer.py
with enterprise-grade reliability features, error handling, and retry mechanisms.

KEY DIFFERENCES FROM BASIC producer.py:
=====================================

1. ERROR HANDLING & RETRIES:
   - Basic producer: Fire-and-forget approach with no error recovery
   - Resilient producer: Automatic retry with exponential backoff for retriable errors
   - Distinguishes between retriable (network issues, timeouts) and non-retriable errors
   - Configurable retry attempts and delay strategies

2. RELIABILITY GUARANTEES:
   - Basic producer: Default settings may lose messages or create duplicates
   - Resilient producer: Idempotent configuration prevents duplicates
   - acks='all' ensures messages are replicated to all in-sync replicas
   - Single in-flight request maintains message ordering

3. MONITORING & OBSERVABILITY:
   - Basic producer: Minimal logging
   - Resilient producer: Comprehensive logging with attempt tracking
   - Detailed error classification and reporting
   - Performance metrics and timing information

4. ASYNC OPERATIONS:
   - Basic producer: Synchronous sends only
   - Resilient producer: Both sync and async sending with callback support
   - Proper future handling and error propagation

5. RESOURCE MANAGEMENT:
   - Basic producer: Manual resource cleanup
   - Resilient producer: Context manager support for automatic cleanup
   - Graceful shutdown with configurable timeouts

WHEN TO USE:
============
- Production environments requiring high reliability
- Systems that cannot afford message loss
- Applications needing automatic error recovery
- Scenarios where message ordering is critical
- Integration with monitoring and alerting systems

WHEN TO USE BASIC producer.py:
==============================
- Development and testing environments
- Simple demonstrations and tutorials
- Non-critical data pipelines
- Learning Kafka concepts
- Prototyping and proof-of-concepts

Usage:
    # Basic usage with retry logic
    with ResilientProducer('localhost:9092', retries=3) as producer:
        metadata = producer.send_message_with_retry('topic', {'data': 'value'})
        
    # Async usage with callbacks
    def callback(error, metadata):
        if error:
            print(f"Send failed: {error}")
        else:
            print(f"Sent to partition {metadata.partition}")
            
    producer.send_message_async('topic', message, callback=callback)
"""

import json
import time
from kafka import KafkaProducer
from kafka.errors import (
    KafkaError, KafkaTimeoutError, RequestTimedOutError,
    NodeNotReadyError, NotLeaderForPartitionError,
    LeaderNotAvailableError, BrokerNotAvailableError,
    CoordinatorNotAvailableError, NetworkExceptionError
)
from logger import get_logger

# Define retriable errors - errors that should trigger retry logic
RETRIABLE_ERRORS = (
    KafkaTimeoutError,
    RequestTimedOutError,
    NodeNotReadyError,
    NotLeaderForPartitionError,
    LeaderNotAvailableError,
    BrokerNotAvailableError,
    CoordinatorNotAvailableError,
    NetworkExceptionError
)


class ResilientProducer:
    """
    A resilient Kafka producer with retry logic, error handling, and reliability features.
    
    This producer provides:
    - Automatic retry with exponential backoff for retriable errors
    - Idempotent configuration to prevent duplicates
    - Proper acknowledgment settings for durability
    - Comprehensive error handling for different error types
    - Ordering guarantees through single in-flight request limitation
    """

    def __init__(self, bootstrap_servers, retries=3, retry_delay=1.0):
        """
        Initialize the resilient producer.
        
        Args:
            bootstrap_servers (str): Comma-separated list of Kafka broker addresses
            retries (int): Maximum number of retries for retriable errors
            retry_delay (float): Base delay between retries in seconds
        """
        self.retries = retries
        self.retry_delay = retry_delay
        self.logger = get_logger("resilient_producer")

        # Configure a producer for reliability and ordering
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            retries=retries,
            max_in_flight_requests_per_connection=1,  # Ensure ordering
            enable_idempotence=True,  # Prevent duplicates
            acks='all',  # Wait for all replicas
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            # Additional reliability settings
            request_timeout_ms=30000,  # 30-second timeout
            retry_backoff_ms=100,  # Base retry backoff
        )

        self.logger.info("ResilientProducer initialized with reliability settings")

    def send_message_with_retry(self, topic, message, key=None):
        """
        Send a message with retry logic and callback handling.
        
        Args:
            topic (str): Kafka topic to send message to
            message (dict): Message payload to send
            key (str, optional): Message key for partitioning
            
        Returns:
            RecordMetadata: Metadata about sent record
            
        Raises:
            KafkaError: For non-retriable errors or after max retries exceeded
        """
        for attempt in range(self.retries + 1):
            try:
                self.logger.debug(f"Sending message to {topic} (attempt {attempt + 1}/{self.retries + 1})")

                # Send a message and wait for acknowledgment
                future = self.producer.send(topic, value=message, key=key)
                record_metadata = future.get(timeout=10)

                self.logger.info(f"Message sent successfully to {topic} - "
                                 f"partition: {record_metadata.partition}, "
                                 f"offset: {record_metadata.offset}")

                return record_metadata

            except RETRIABLE_ERRORS as e:
                if attempt < self.retries:
                    # Calculate exponential backoff delay
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"Retriable error on attempt {attempt + 1}: {e}. "
                                        f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    self.logger.error(f"Max retries ({self.retries}) exceeded for retriable error: {e}")
                    raise e

            except KafkaError as e:
                # Non-retriable error - fail immediately
                self.logger.error(f"Non-retriable Kafka error: {e}")
                raise e
            except Exception as e:
                # Unexpected error
                self.logger.error(f"Unexpected error while sending message: {e}")
                raise KafkaError(f"Unexpected error: {e}")

        # This should never be reached due to the exception handling above,
        # but included for completeness to ensure all code paths return a value
        raise KafkaError("Unexpected end of retry loop without result")

    def send_message_async(self, topic, message, key=None, callback=None):
        """
        Send a message asynchronously with an optional callback.
        
        Args:
            topic (str): Kafka topic to send message to
            message (dict): Message payload to send
            key (str, optional): Message key for partitioning
            callback (callable, optional): Callback function for handling a result
            
        Returns:
            FutureRecordMetadata: Future object for the send operation
        """
        try:
            future = self.producer.send(topic, value=message, key=key)

            if callback:
                # Add callback to handle success/failure
                future.add_callback(lambda metadata: callback(None, metadata))
                future.add_errback(lambda error: callback(error, None))

            self.logger.debug(f"Async message sent to {topic}")
            return future

        except Exception as e:
            self.logger.error(f"Error in async send: {e}")
            if callback:
                callback(e, None)
            raise

    def flush(self, timeout=None):
        """
        Flush all buffered messages.
        
        Args:
            timeout (float, optional): Timeout in seconds for flush operation
        """
        try:
            self.logger.debug("Flushing producer buffer...")
            self.producer.flush(timeout=timeout)
            self.logger.info("Producer buffer flushed successfully")
        except Exception as e:
            self.logger.error(f"Error flushing producer: {e}")
            raise

    def close(self, timeout=None):
        """
        Close the producer and release resources.
        
        Args:
            timeout (float, optional): Timeout in seconds for close operation
        """
        try:
            self.logger.info("Closing resilient producer...")
            self.producer.close(timeout=timeout)
            self.logger.info("Resilient producer closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing producer: {e}")
            raise

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure producer is closed."""
        self.close()


def example_usage():
    """Example usage of the ResilientProducer."""
    import os

    # Configuration from environment variables
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.environ.get("KAFKA_TOPIC", "resilient-test-topic")

    # Create resilient producer with context manager
    with ResilientProducer(bootstrap_servers, retries=3, retry_delay=1.0) as producer:

        # Example messages
        messages = [
            {"id": 1, "event_type": "user_created", "user_id": "user123", "timestamp": time.time()},
            {"id": 2, "event_type": "user_updated", "user_id": "user123", "data": {"name": "John Doe"}},
            {"id": 3, "event_type": "order_placed", "order_id": "order456", "user_id": "user123", "amount": 99.99}
        ]

        # Send messages with retry logic
        for message in messages:
            try:
                key = message.get("user_id") or message.get("order_id")
                metadata = producer.send_message_with_retry(topic, message, key=key)
                print(f"✅ Sent: {message} -> partition: {metadata.partition}, offset: {metadata.offset}")

            except Exception as e:
                print(f"❌ Failed to send message {message}: {e}")

        # Example of async sending with callback
        def message_callback(error, metadata):
            if error:
                print(f"❌ Async send failed: {error}")
            else:
                print(f"✅ Async send succeeded: partition={metadata.partition}, offset={metadata.offset}")

        async_message = {"id": 4, "event_type": "async_test", "data": "async message"}
        producer.send_message_async(topic, async_message, callback=message_callback)

        # Ensure all messages are sent
        producer.flush()


if __name__ == "__main__":
    example_usage()
