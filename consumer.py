import os

# required to properly collect coverage from subprocesses
if os.getenv("COVERAGE_PROCESS_START"):
    import coverage

    coverage.process_startup()

from kafka import KafkaConsumer
from logger import get_logger
import argparse
import json

parser = argparse.ArgumentParser(description="Kafka Event Consumer")
parser.add_argument("-e", "--event-type", help="Filter by event_type (optional)", required=False)
parser.add_argument("-g", "--group-id", help="Kafka consumer group ID (optional)", required=False)
parser.add_argument("-t", "--test-mode", action="store_true")
args = parser.parse_args()

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


def consume_events(topic, consumer_args, event_type=None, group_id=None):
    """
    Consume messages from a Kafka topic.

    This function creates a Kafka consumer with the provided arguments and listens
    to a specified topic for incoming messages. Messages are parsed as JSON where
    possible and logged appropriately. Filtering is available based on an optional
    event type attribute in the message.

    :param topic: Kafka topic to consume messages from.
    :param consumer_args: Dictionary of arguments to configure the KafkaConsumer.
    :param event_type: Optional. Filters messages by the `event_type` attribute if it's included in the message payload.
    """
    consumer = KafkaConsumer(topic, **consumer_args)

    logger = get_logger("consumer")

    logger.info(f"Polyglot consumer listening, consumer group: {group_id}\n")

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
                if event_type and parsed.get("event_type") != event_type:
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


def main():
    """Main function that runs when the script is executed directly"""
    kafka_topic = os.environ.get("KAFKA_TOPIC", "test-topic")
    kafka_bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    # Initialize the Kafka consumer with configuration
    # - bootstrap_servers: Connection string for the Kafka broker
    # - auto_offset_reset='earliest': Start reading from the beginning of the topic if no committed offset exists
    # - enable_auto_commit=True: Automatically commit offsets
    kafka_consumer_args = {
        'bootstrap_servers': kafka_bootstrap_servers,
        'auto_offset_reset': 'earliest',
        'enable_auto_commit': True
    }

    if args.group_id:
        kafka_consumer_args['group_id'] = args.group_id

    if args.test_mode:
        kafka_consumer_args['consumer_timeout_ms'] = 3000  # pragma: no cover

    consume_events(kafka_topic, kafka_consumer_args, args.event_type, args.group_id)


if __name__ == "__main__":
    main()
