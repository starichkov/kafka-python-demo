from testcontainers.kafka import KafkaContainer
import subprocess
import time
import os


def test_producer_and_consumer_via_scripts(tmp_path):
    topic = "test-topic"

    with KafkaContainer(image="confluentinc/cp-kafka:7.9.2") as kafka:
        bootstrap_servers = kafka.get_bootstrap_server()

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
        result = subprocess.run(
            ["python", "consumer.py", "--test-mode"],
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert "note event" in result.stdout.lower()
