"""
Resilient Kafka Consumer with Error Handling and Dead Letter Queue

This module provides a robust Kafka consumer implementation that extends the basic consumer.py
with enterprise-grade reliability features, error handling, retry mechanisms, and dead letter queue patterns.

KEY DIFFERENCES FROM BASIC consumer.py:
======================================

1. ERROR HANDLING & RETRY MECHANISMS:
   - Basic consumer: Simple message processing with basic exception handling
   - Resilient consumer: Sophisticated retry logic with exponential backoff
   - Distinguishes between retriable and non-retriable errors
   - Configurable retry attempts and delay strategies

2. OFFSET MANAGEMENT:
   - Basic consumer: Auto-commit enabled by default (fire-and-forget)
   - Resilient consumer: Manual offset management for precise control
   - Commits only after successful processing to prevent message loss
   - Handles commit failures gracefully

3. DEAD LETTER QUEUE (DLQ) PATTERN:
   - Basic consumer: Failed messages are lost or cause processing to stop
   - Resilient consumer: Failed messages are sent to a dead letter queue
   - Preserves original message metadata and error information
   - Enables later analysis and reprocessing of failed messages

4. BATCH PROCESSING:
   - Basic consumer: Single message processing only
   - Resilient consumer: Both single message and batch processing modes
   - Configurable batch sizes and timeouts
   - Optimized for high-throughput scenarios

5. MONITORING & OBSERVABILITY:
   - Basic consumer: Basic logging with message content
   - Resilient consumer: Comprehensive logging with processing statistics
   - Detailed error classification and tracking
   - Offset management and commit status reporting

6. RESOURCE MANAGEMENT:
   - Basic consumer: Manual resource cleanup
   - Resilient consumer: Context manager support for automatic cleanup
   - Graceful shutdown handling with proper resource release

7. FAULT TOLERANCE:
   - Basic consumer: Processing stops on errors
   - Resilient consumer: Continues processing despite individual message failures
   - Isolates failures to prevent cascading issues
   - Maintains processing continuity

WHEN TO USE:
============
- Production environments requiring high reliability
- Systems where message processing failures must be tracked
- Applications that cannot afford to lose failed messages
- High-throughput scenarios requiring batch processing
- Integration with monitoring and alerting systems
- Scenarios requiring precise offset control

WHEN TO USE BASIC consumer.py:
==============================
- Development and testing environments
- Simple demonstrations and tutorials
- Non-critical data processing pipelines
- Learning Kafka concepts
- Prototyping and proof-of-concepts
- Simple event logging scenarios

Usage:
    # Basic usage with error handling and DLQ
    def process_message(message):
        # Your processing logic here
        if some_error_condition:
            raise RetryableException("This will be retried")
        elif fatal_condition:
            raise ValueError("This goes directly to DLQ")
    
    with ResilientConsumer(servers, ['topic'], 'group', 'dlq-topic') as consumer:
        consumer.process_messages(process_message, max_retries=3)
        
    # Batch processing for high throughput
    def process_batch(messages):
        # Process multiple messages together
        for msg in messages:
            # batch processing logic
            pass
    
    consumer.process_messages_batch(process_batch, batch_size=50, batch_timeout=5.0)
"""

import json
import time
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import CommitFailedError
from logger import get_logger


class RetryableException(Exception):
    """Exception that indicates the operation should be retried."""
    pass


def _safe_deserialize(value):
    """
    Safely deserialize the message value, falling back to string if JSON parsing fails.

    Args:
        value (bytes): Raw message value

    Returns:
        dict or str: Parsed JSON or string value
    """
    try:
        return json.loads(value.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return value.decode('utf-8', errors='replace')


class ResilientConsumer:
    """
    A resilient Kafka consumer with error handling, dead letter queue, and manual offset management.
    
    This consumer provides:
    - Manual offset management for better control
    - Dead letter queue pattern for failed messages
    - Retry logic with exponential backoff
    - Comprehensive error handling and recovery
    - Batch processing capabilities
    """

    def __init__(self, bootstrap_servers, topics, group_id, dlq_topic=None):
        """
        Initialize the resilient consumer.
        
        Args:
            bootstrap_servers (str): Comma-separated list of Kafka broker addresses
            topics (list): List of topics to consume from
            group_id (str): Consumer group ID
            dlq_topic (str, optional): Dead letter queue topic name
        """
        self.topics = topics
        self.group_id = group_id
        self.dlq_topic = dlq_topic
        self.logger = get_logger("resilient_consumer")

        # Configure consumer for reliability
        self.consumer = KafkaConsumer(
            *self.topics,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            enable_auto_commit=False,  # Manual commit for reliability
            max_poll_records=10,  # Process in small batches
            auto_offset_reset='earliest',
            value_deserializer=lambda v: _safe_deserialize(v),
            key_deserializer=lambda k: k.decode('utf-8') if k else None
        )

        # Dead letter queue producer (if enabled)
        self.dlq_producer = None
        if dlq_topic:
            self.dlq_producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',  # Ensure DLQ messages are persisted
                retries=3
            )
            self.logger.info(f"Dead letter queue enabled: {dlq_topic}")

        self.logger.info(f"ResilientConsumer initialized for topics: {self.topics}, group: {group_id}")

    def process_messages(self, message_handler, max_retries=3, retry_delay=1.0):
        """
        Process messages with error handling and DLQ support.
        
        Args:
            message_handler (callable): Function to process each message
            max_retries (int): Maximum number of retries for retriable errors
            retry_delay (float): Base delay between retries in seconds
        """
        try:
            self.logger.info("Starting message processing...")

            for message in self.consumer:
                retry_count = 0
                success = False

                self.logger.debug(f"Processing message: topic={message.topic}, "
                                  f"partition={message.partition}, offset={message.offset}")

                while retry_count <= max_retries and not success:
                    try:
                        # Process the message
                        message_handler(message)

                        # Commit offset after successful processing
                        self.consumer.commit()
                        success = True

                        self.logger.debug(f"Message processed successfully: "
                                          f"topic={message.topic}, partition={message.partition}, "
                                          f"offset={message.offset}")

                    except RetryableException as e:
                        retry_count += 1
                        if retry_count > max_retries:
                            self.logger.error(f"Max retries ({max_retries}) exceeded for retriable error: {e}")
                            self._send_to_dlq(message, str(e), "max_retries_exceeded")
                            self.consumer.commit()  # Commit to skip this message
                        else:
                            # Exponential backoff
                            delay = retry_delay * (2 ** (retry_count - 1))
                            self.logger.warning(f"Retriable error on attempt {retry_count}: {e}. "
                                                f"Retrying in {delay} seconds...")
                            time.sleep(delay)

                    except Exception as e:
                        # Non-retryable error - send to DLQ immediately
                        self.logger.error(f"Non-retryable error processing message: {e}")
                        self._send_to_dlq(message, str(e), "non_retryable_error")
                        self.consumer.commit()  # Commit to skip this message
                        break

        except KeyboardInterrupt:
            self.logger.info("Shutting down gracefully...")
        except Exception as e:
            self.logger.error(f"Unexpected error in message processing: {e}")
            raise
        finally:
            self.close()

    def process_messages_batch(self, batch_handler, batch_size=10, batch_timeout=5.0, max_retries=3):
        """
        Process messages in batches for better throughput.
        
        Args:
            batch_handler (callable): Function to process a batch of messages
            batch_size (int): Maximum number of messages per batch
            batch_timeout (float): Maximum time to wait for batch completion
            max_retries (int): Maximum retries for failed batches
        """
        batch = []  # Initialize batch outside try block to ensure it's always defined

        try:
            self.logger.info(f"Starting batch processing (size={batch_size}, timeout={batch_timeout}s)...")

            batch_start_time = time.time()

            for message in self.consumer:
                batch.append(message)

                # Process batch if size limit reached or timeout exceeded
                if (len(batch) >= batch_size or
                        time.time() - batch_start_time > batch_timeout):
                    self._process_batch(batch, batch_handler, max_retries)
                    batch.clear()
                    batch_start_time = time.time()

        except KeyboardInterrupt:
            # Process remaining messages in a batch
            if batch:
                self._process_batch(batch, batch_handler, max_retries)
            self.logger.info("Shutting down gracefully...")
        except Exception as e:
            self.logger.error(f"Unexpected error in batch processing: {e}")
            raise
        finally:
            self.close()

    def _process_batch(self, batch, batch_handler, max_retries):
        """
        Process a batch of messages with error handling.
        
        Args:
            batch (list): List of messages to process
            batch_handler (callable): Function to process the batch
            max_retries (int): Maximum retries for failed batches
        """
        for attempt in range(max_retries + 1):
            try:
                batch_handler(batch)
                self.consumer.commit()  # Commit after successful batch processing
                self.logger.debug(f"Batch of {len(batch)} messages processed successfully")
                return

            except RetryableException as e:
                if attempt < max_retries:
                    delay = 1.0 * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(f"Retriable batch error on attempt {attempt + 1}: {e}. "
                                        f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Batch processing failed after {max_retries} retries: {e}")
                    self._handle_failed_batch(batch, str(e), "batch_max_retries_exceeded")
                    return

            except Exception as e:
                self.logger.error(f"Non-retryable batch processing error: {e}")
                self._handle_failed_batch(batch, str(e), "batch_non_retryable_error")
                return

        # This should never be reached due to the exception handling above,
        # but included for completeness to ensure all code paths return
        self.logger.warning("Unexpected end of batch retry loop without resolution")
        return

    def _handle_failed_batch(self, batch, error_reason, error_type):
        """
        Handle a failed batch by sending individual messages to DLQ or processing them individually.
        
        Args:
            batch (list): Failed batch of messages
            error_reason (str): Reason for batch failure
            error_type (str): Type of error that occurred
        """
        self.logger.info(f"Handling failed batch of {len(batch)} messages...")

        for message in batch:
            self._send_to_dlq(message, error_reason, error_type)

        # Commit offsets to skip the failed batch
        self.consumer.commit()

    def _send_to_dlq(self, original_message, error_reason, error_type):
        """
        Send a failed message to the dead letter queue.
        
        Args:
            original_message: Original Kafka message that failed
            error_reason (str): Reason for the failure
            error_type (str): Type of error (e.g., 'max_retries_exceeded', 'non_retryable_error')
        """
        if not self.dlq_producer or not self.dlq_topic:
            self.logger.warning(f"No DLQ configured - dropping failed message: {error_reason}")
            return

        try:
            # Create DLQ message with metadata
            dlq_message = {
                "original_topic": original_message.topic,
                "original_partition": original_message.partition,
                "original_offset": original_message.offset,
                "original_key": original_message.key,
                "original_value": original_message.value if isinstance(original_message.value, (dict, list)) else str(
                    original_message.value),
                "original_timestamp": getattr(original_message, 'timestamp', None),
                "error_reason": error_reason,
                "error_type": error_type,
                "failed_at": time.time(),
                "consumer_group": self.group_id
            }

            # Send to DLQ with an original key for partitioning
            future = self.dlq_producer.send(
                self.dlq_topic,
                value=dlq_message,
                key=original_message.key
            )

            # Wait for sent confirmation
            future.get(timeout=5)

            self.logger.info(f"Message sent to DLQ: topic={original_message.topic}, "
                             f"partition={original_message.partition}, offset={original_message.offset}, "
                             f"error={error_type}")

        except Exception as dlq_error:
            self.logger.error(f"Failed to send message to DLQ: {dlq_error}")
            # Could implement additional fallback here (file logging, etc.)

    def commit_sync(self):
        """
        Synchronously commit current offsets.
        """
        try:
            self.consumer.commit()
            self.logger.debug("Offsets committed successfully")
        except CommitFailedError as e:
            self.logger.error(f"Failed to commit offsets: {e}")
            raise

    def seek_to_beginning(self, partitions=None):
        """
        Seek to the beginning of partitions.
        
        Args:
            partitions (list, optional): List of TopicPartition objects. If None, seeks all assigned partitions.
        """
        if partitions:
            self.consumer.seek_to_beginning(*partitions)
        else:
            self.consumer.seek_to_beginning()
        self.logger.info("Seeked to beginning of partitions")

    def get_current_offsets(self):
        """
        Get current committed offsets for assigned partitions.
        
        Returns:
            dict: Dictionary mapping TopicPartition to OffsetAndMetadata
        """
        try:
            assigned_partitions = self.consumer.assignment()
            committed_offsets = {}

            # The committed() method only accepts a single TopicPartition, not a collection
            for partition in assigned_partitions:
                offset_metadata = self.consumer.committed(partition, metadata=True)
                if offset_metadata is not None:
                    committed_offsets[partition] = offset_metadata

            return committed_offsets
        except Exception as e:
            self.logger.error(f"Failed to get current offsets: {e}")
            return {}

    def close(self):
        """
        Close the consumer and DLQ producer, releasing resources.
        """
        try:
            self.logger.info("Closing resilient consumer...")

            if self.consumer:
                self.consumer.close()

            if self.dlq_producer:
                self.dlq_producer.close()

            self.logger.info("Resilient consumer closed successfully")

        except Exception as e:
            self.logger.error(f"Error closing consumer: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure resources are closed."""
        self.close()


def example_usage():
    """Example usage of the ResilientConsumer."""
    import os

    # Configuration from environment variables
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.environ.get("KAFKA_TOPIC", "resilient-test-topic")
    dlq_topic = os.environ.get("KAFKA_DLQ_TOPIC", "resilient-test-topic-dlq")
    group_id = "resilient-consumer-group"

    def process_message(message):
        """Example message processing function."""
        print(f"Processing: key={message.key}, value={message.value}")

        # Simulate processing logic
        if isinstance(message.value, dict):
            event_type = message.value.get("event_type")

            # Simulate retriable error for certain messages
            if event_type == "error_test":
                raise RetryableException("Simulated retriable error")

            # Simulate non-retriable error
            if event_type == "fatal_error":
                raise ValueError("Simulated non-retriable error")

            print(f"✅ Processed {event_type} event successfully")
        else:
            print(f"✅ Processed text message: {message.value}")

    def process_batch(messages):
        """Example batch processing function."""
        print(f"Processing batch of {len(messages)} messages")

        for message in messages:
            # Simulate batch processing
            if isinstance(message.value, dict) and message.value.get("event_type") == "batch_error":
                raise RetryableException("Simulated batch processing error")

        print(f"✅ Batch of {len(messages)} messages processed successfully")

    # Example 1: Single message processing with DLQ
    print("=== Example 1: Single Message Processing ===")
    with ResilientConsumer(bootstrap_servers, [topic], group_id, dlq_topic) as consumer:
        try:
            consumer.process_messages(process_message, max_retries=2, retry_delay=0.5)
        except KeyboardInterrupt:
            print("Stopped by user")

    # Example 2: Batch processing
    print("\n=== Example 2: Batch Processing ===")
    with ResilientConsumer(bootstrap_servers, [topic], f"{group_id}-batch", dlq_topic) as consumer:
        try:
            consumer.process_messages_batch(process_batch, batch_size=5, batch_timeout=3.0)
        except KeyboardInterrupt:
            print("Stopped by user")


if __name__ == "__main__":
    example_usage()
