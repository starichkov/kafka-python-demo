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
