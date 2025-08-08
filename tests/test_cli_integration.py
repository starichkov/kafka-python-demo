"""
Integration Tests for Kafka Producer and Consumer CLI Scripts

This test module provides end-to-end integration testing for the Kafka producer and consumer
command-line scripts. It uses testcontainers to spin up a real Kafka instance and tests
the complete workflow of producing and consuming messages through the CLI scripts.

The tests cover:
- Producer script generating JSON messages and a consumer script processing them
- Consumer script handling plain text messages (polyglot functionality)
- Proper message formatting and logging output verification

These tests ensure that the CLI scripts work correctly in a real Kafka environment
and can handle different message formats as intended.
"""

from testcontainers.kafka import KafkaContainer
import subprocess
import time
import os
from kafka import KafkaProducer
import pytest


@pytest.fixture(scope="module")
def kafka_container():
    """Fixture that provides a reusable Kafka container for all tests."""
    with KafkaContainer(image="confluentinc/cp-kafka:7.9.2") as kafka:
        yield kafka


def test_producer_and_consumer_via_scripts(tmp_path, kafka_container):
    """
    Test the end-to-end workflow of producer and consumer CLI scripts.

    This test runs the producer.py script to generate sample JSON messages,
    then runs the consumer.py script in test mode to consume those messages.
    It verifies that the consumer correctly processes the JSON messages
    produced by the producer script.

    Args:
        tmp_path: pytest fixture providing temporary directory path
        kafka_container: pytest fixture providing Kafka testcontainer instance

    Asserts:
        - Consumer output contains "note event" indicating successful message processing
    """
    topic = "test-topic-producer-consumer-scripts"

    bootstrap_servers = kafka_container.get_bootstrap_server()

    env = os.environ.copy()
    env["KAFKA_BOOTSTRAP_SERVERS"] = bootstrap_servers
    env["KAFKA_TOPIC"] = topic

    # 1. Run the producer
    subprocess.run(
        ["python", "producer.py"],
        env=env,
        check=True,
    )

    time.sleep(1)

    # 2. Capture consumer output
    env["COVERAGE_PROCESS_START"] = ".coveragerc"  # Enable coverage for subprocess

    result = subprocess.run(
        ["python", "consumer.py", "--test-mode"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert "note event" in result.stdout.lower()


def test_plain_text_consumer(tmp_path, kafka_container):
    """
    Test consumer's ability to handle plain text messages (polyglot functionality).

    This test verifies that the consumer script can properly process non-JSON messages
    by sending a plain text message to Kafka and confirming the consumer displays it
    with the correct "📦 Plain" prefix, demonstrating the polyglot consumer capability.

    Args:
        tmp_path: pytest fixture providing temporary directory path
        kafka_container: pytest fixture providing Kafka testcontainer instance

    Asserts:
        - Consumer output contains "📦 Plain" prefix for plain text messages
        - Consumer output contains the original plain text message content
    """
    topic = "test-topic-plain-text-consumer"

    bootstrap_servers = kafka_container.get_bootstrap_server()

    # Create a producer that sends plain text messages
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        value_serializer=lambda v: v.encode('utf-8')  # Plain text serializer
    )

    # Send a plain text message
    plain_text_message = "This is a plain text message"
    producer.send(topic, key="plain-text-key", value=plain_text_message)
    producer.flush()

    time.sleep(1)

    # Run the consumer and capture its output
    env = os.environ.copy()
    env["KAFKA_BOOTSTRAP_SERVERS"] = bootstrap_servers
    env["KAFKA_TOPIC"] = topic
    env["COVERAGE_PROCESS_START"] = ".coveragerc"  # Enable coverage for subprocess

    result = subprocess.run(
        ["python", "consumer.py", "--test-mode"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Verify that the plain text message was processed correctly
    assert "📦 Plain" in result.stdout
    assert plain_text_message in result.stdout
