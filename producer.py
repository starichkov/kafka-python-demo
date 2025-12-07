import os

# required to properly collect coverage from subprocesses
if os.getenv("COVERAGE_PROCESS_START"):
    import coverage

    coverage.process_startup()

from kafka import KafkaProducer
from logger import get_logger
import time
from serialization import SERIALIZERS, CONTENT_TYPES

"""
Apache Kafka Producer Demo

This script demonstrates how to produce JSON messages to an Apache Kafka topic.
It creates a series of simple JSON messages and sends them to a topic
(configurable via KAFKA_TOPIC environment variable, defaults to 'notes-topic')
on a Kafka broker (configurable via KAFKA_BOOTSTRAP_SERVERS environment variable).

The producer is configured to automatically serialize Python dictionaries to JSON
before sending them to Kafka.

Usage:
    python producer.py
"""

EVENT_TYPES = ["note_created", "note_updated", "note_deleted"]


def produce_events(bootstrap_servers, topic):
    """
    Produce a series of sample events to a Kafka topic.

    This function creates a Kafka producer and sends 9 sample messages to the specified
    topic. Each message contains JSON data with an ID, event type, and descriptive text.
    The events cycle through three types: note_created, note_updated, and note_deleted.

    Args:
        bootstrap_servers (str): Comma-separated list of Kafka broker addresses
                                (e.g., 'localhost:9092' or 'broker1:9092,broker2:9092')
        topic (str): Name of the Kafka topic to send messages to

    Example:
        >>> produce_events('localhost:9092', 'my-topic')
        # Sends 9 messages with different event types to 'my-topic'
    """
    # Initialize the Kafka producer with configuration
    # - bootstrap_servers: Connection string for the Kafka broker
    # - value_serializer: Function to convert Python objects to bytes
    #   (in this case, converting dictionaries to JSON strings and then to UTF-8 bytes)
    message_format = os.environ.get("MESSAGE_FORMAT", "json").lower()

    value_serializer = SERIALIZERS.get(message_format, SERIALIZERS["json"])
    content_type = CONTENT_TYPES.get(message_format, CONTENT_TYPES["json"]).encode("ascii")

    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=value_serializer,
    )

    logger = get_logger("producer")

    # Send 9 sample messages to the Kafka topic
    for i, event_type in enumerate(EVENT_TYPES * 3):
        # Create a simple message with an ID and text
        message = {"id": i, "event_type": event_type, "text": f"Note event {i} of type {event_type}"}

        # Send the message to the topic from the environment variable
        headers = [("content-type", content_type)]
        producer.send(topic, key=event_type, value=message, headers=headers)

        # Print confirmation and wait 1 second between messages
        logger.info(f"Sent: key={event_type} | value={message}")
        time.sleep(1)

    # Ensure all messages are sent before exiting
    producer.flush()


def main():
    """Main function that runs when the script is executed directly"""
    kafka_bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_topic = os.environ.get("KAFKA_TOPIC", "notes-topic")

    produce_events(kafka_bootstrap_servers, kafka_topic)


if __name__ == "__main__":
    main()
