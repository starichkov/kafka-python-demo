from kafka import KafkaProducer
from logger import get_logger
import json
import time
import os

"""
Apache Kafka Producer Demo

This script demonstrates how to produce JSON messages to an Apache Kafka topic.
It creates a series of simple JSON messages and sends them to 'test-topic' on
a local Kafka broker.

The producer is configured to automatically serialize Python dictionaries to JSON
before sending them to Kafka.

Usage:
    python producer.py
"""

EVENT_TYPES = ["note_created", "note_updated", "note_deleted"]

bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Initialize the Kafka producer with configuration
# - bootstrap_servers: Connection string for the Kafka broker
# - value_serializer: Function to convert Python objects to bytes
#   (in this case, converting dictionaries to JSON strings and then to UTF-8 bytes)
producer = KafkaProducer(
    bootstrap_servers=bootstrap_servers,
    key_serializer=lambda k: k.encode('utf-8'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

logger = get_logger("producer")

# Send 9 sample messages to the Kafka topic
for i, event_type in enumerate(EVENT_TYPES * 3):
    # Create a simple message with an ID and text
    message = {"id": i, "event_type": event_type, "text": f"Note event {i} of type {event_type}"}

    # Send the message to 'test-topic'
    producer.send('test-topic', key=event_type, value=message)

    # Print confirmation and wait 1 second between messages
    logger.info(f"Sent: key={event_type} | value={message}")
    time.sleep(1)

# Ensure all messages are sent before exiting
producer.flush()
