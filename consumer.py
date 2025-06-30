import os

# required to properly collect coverage from subprocesses
if os.getenv("COVERAGE_PROCESS_START"):
    import coverage

    coverage.process_startup()

from kafka import KafkaConsumer
from logger import get_logger
import argparse
import json

"""
Apache Kafka Consumer Demo

This script demonstrates how to consume messages from an Apache Kafka topic.
It can handle both JSON and plain text messages, providing a polyglot consumer
that's useful in environments where different systems produce data in different formats.

The consumer connects to a Kafka broker (configurable via KAFKA_BOOTSTRAP_SERVERS environment variable),
subscribes to a topic (configurable via KAFKA_TOPIC environment variable, defaults to 'test-topic'),
and processes incoming messages until interrupted with Ctrl+C.

Usage:
    python consumer.py
"""


def try_parse_json(value: bytes):
    """
    Attempts to parse a byte string as JSON, falling back to plain text if parsing fails.

    Args:
        value (bytes): The raw message value from Kafka

    Returns:
        dict or str: Parsed JSON as dictionary if successful, or string if parsing fails
    """
    try:
        return json.loads(value.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return value.decode('utf-8', errors='replace')


parser = argparse.ArgumentParser(description="Kafka Event Consumer")
parser.add_argument("-e", "--event-type", help="Filter by event_type (optional)", required=False)
parser.add_argument("-g", "--group-id", help="Kafka consumer group ID (optional)", required=False)
parser.add_argument("-t", "--test-mode", action="store_true")
args = parser.parse_args()


def main():
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.environ.get("KAFKA_TOPIC", "test-topic")

    # Initialize the Kafka consumer with configuration
    # - topic: The Kafka topic to subscribe to (from environment variable)
    # - bootstrap_servers: Connection string for the Kafka broker
    # - auto_offset_reset='earliest': Start reading from the beginning of the topic if no committed offset exists
    # - enable_auto_commit=True: Automatically commit offsets
    consumer_args = {
        'bootstrap_servers': bootstrap_servers,
        'auto_offset_reset': 'earliest',
        'enable_auto_commit': True
    }

    if args.group_id:
        consumer_args['group_id'] = args.group_id

    if args.test_mode:
        consumer_args['consumer_timeout_ms'] = 3000  # pragma: no cover

    consumer = KafkaConsumer(topic, **consumer_args)

    logger = get_logger("consumer")

    logger.info(f"Polyglot consumer listening, consumer group: {args.group_id}\n")

    try:
        # Continuously poll for new messages
        for message in consumer:
            # Try to parse the message as JSON, fall back to plain text if not valid JSON
            parsed = try_parse_json(message.value)

            # Decode key if available
            key = message.key.decode('utf-8') if message.key else None
            partition = message.partition
            offset = message.offset

            # Display the message with an appropriate prefix based on its type
            if isinstance(parsed, dict):
                if args.event_type and parsed.get("event_type") != args.event_type:
                    continue  # Skip non-matching event
                logger.info(
                    f"✅ JSON ({parsed['event_type']}) | key={key} | partition={partition} | offset={offset} → {parsed}")
            else:
                logger.info(f"📦 Plain | key={key} | partition={partition} | offset={offset} → {parsed}")
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        logger.info("\nShutting down gracefully...")
    finally:
        # Always close the consumer to release resources
        consumer.close()


if __name__ == "__main__":
    main()
