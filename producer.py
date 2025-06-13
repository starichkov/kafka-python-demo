from kafka import KafkaProducer
import json
import random
import time

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

# Initialize the Kafka producer with configuration
# - bootstrap_servers: Connection string for the Kafka broker
# - value_serializer: Function to convert Python objects to bytes
#   (in this case, converting dictionaries to JSON strings and then to UTF-8 bytes)
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Send 5 sample messages to the Kafka topic
for i in range(10):
    event_type = random.choice(EVENT_TYPES)

    # Create a simple message with an ID and text
    message = {"id": i, "event_type": event_type, "text": f"Note event {i} of type {event_type}"}

    # Send the message to 'test-topic'
    producer.send('test-topic', message)

    # Print confirmation and wait 1 second between messages
    print(f"Sent: {message}")
    time.sleep(1)

# Ensure all messages are sent before exiting
producer.flush()
