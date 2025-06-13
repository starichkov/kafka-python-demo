from kafka import KafkaConsumer
import argparse
import json

"""
Apache Kafka Consumer Demo

This script demonstrates how to consume messages from an Apache Kafka topic.
It can handle both JSON and plain text messages, providing a polyglot consumer
that's useful in environments where different systems produce data in different formats.

The consumer connects to a local Kafka broker, subscribes to 'test-topic',
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
parser.add_argument("-t", "--event-type", help="Filter by event_type", required=False)
args = parser.parse_args()

# Initialize the Kafka consumer with configuration
# - 'test-topic': The Kafka topic to subscribe to
# - bootstrap_servers: Connection string for the Kafka broker
# - auto_offset_reset='earliest': Start reading from the beginning of the topic if no committed offset exists
# - enable_auto_commit=True: Automatically commit offsets
consumer = KafkaConsumer(
    'test-topic',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True
)

print("Polyglot consumer listening...\n")

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
            print(f"✅ JSON ({parsed['event_type']}) | key={key} | partition={partition} | offset={offset} → {parsed}")
        else:
            print(f"📦 Plain | key={key} | partition={partition} | offset={offset} → {parsed}")
except KeyboardInterrupt:
    # Handle graceful shutdown on Ctrl+C
    print("\nShutting down gracefully...")
finally:
    # Always close the consumer to release resources
    consumer.close()
