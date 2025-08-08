[![Author](https://img.shields.io/badge/Author-Vadim%20Starichkov-blue?style=for-the-badge)](https://github.com/starichkov)
[![GitHub License](https://img.shields.io/github/license/starichkov/kafka-python-demo?style=for-the-badge)](https://github.com/starichkov/kafka-python-demo/blob/main/LICENSE.md)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/starichkov/kafka-python-demo/python.yml?style=for-the-badge)](https://github.com/starichkov/kafka-python-demo/actions/workflows/python.yml)
[![Codecov](https://img.shields.io/codecov/c/github/starichkov/kafka-python-demo?style=for-the-badge)](https://codecov.io/gh/starichkov/kafka-python-demo)

# Apache Kafka Python Demo

## 🧩 Overview

A minimal Apache Kafka demo using Python featuring:
- A **JSON-producing** `producer.py`
- A **format-tolerant** `consumer.py` supporting JSON & plain text
- Partition-awareness, message keying, and consumer group support
- Integration testing via `Testcontainers`
- GitHub Actions & Codecov integration

It’s designed to simulate a polyglot messaging environment, where different systems or services might produce data in different formats to the same Apache Kafka topic.

---

## ⚙️ Requirements

- Python 3.10+
- Docker & Docker Compose (for container-based setup)
- Apache Kafka (external or Dockerized)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## 🚀 Running the Demo

### 1. Start Apache Kafka

You can start Apache Kafka using Docker. For example:

```shell
docker run -d --name kafka-391 \
  -p 9092:9092 \
  apache/kafka:3.9.1
```

More information about helper scripts Kafka provides could be found in a [separate section](documentation/kafka.md).

### 🟢 Run Producer

```bash
python producer.py
```

Produces random JSON events (`note_created`, `note_updated`, `note_deleted`) with message keys for partitioning.

### 🔵 Run Consumer

```bash
python consumer.py                   # All events
python consumer.py --event-type X   # Filtered by event_type
python consumer.py --group-id my-group
```

Displays event type, partition, and offset info.

---

### 🔑 Message Keys and Partitions

The producer now uses the message's `event_type` as the Kafka **key**, which ensures that:

- All events of the same type (e.g. `note_created`) are sent to the **same partition**
- Kafka can guarantee **ordering per event type**

The consumer now displays Kafka metadata per message, including:

- **Key** — the event type used for partitioning
- **Partition** — which partition the message was written to
- **Offset** — the message's position in the partition log

This helps visualize how Kafka distributes messages based on keys.

Example output:

```
✅ JSON (note_created) | key=note_created | partition=1 | offset=42 → {...}
```

**Note:** Kafka's key-based partitioning uses an internal hash function.
With a small number of keys (e.g., only `note_created`, `note_updated`, and `note_deleted`), multiple keys may hash to the same partition.

As a result:
- You may see **some partitions receive no messages**
- This is expected behavior with small key sets
- Kafka **guarantees same key → same partition**, but **not even distribution** across partitions

To see all partitions used, try increasing the number of unique keys or remove the key to enable round-robin distribution.

---

### 👥 Consumer Groups and Partition Rebalancing

Kafka uses consumer groups to distribute the workload of processing messages across multiple consumers.

- Consumers in the **same group** share topic partitions — each partition is consumed by only **one group member**
- If a consumer **joins or leaves** the group, Kafka triggers a **rebalance**
- Kafka automatically assigns partitions based on availability and group size

This project supports an optional `--group-id` parameter in the consumer:

```shell
python consumer.py --group-id demo-group
```

Running multiple consumers with the same group ID simulates real-world partition-based load balancing. You can observe which partitions each consumer receives by inspecting the output:

```
✅ JSON (note_created) | key=note_created | partition=2 | offset=15 → ...
```

Note: If you have more partitions than consumers, some consumers may receive multiple partitions. If you have more consumers than partitions, some may remain idle.

---

## 🧪 Testing & Coverage

Install dev requirements:

```bash
pip install -r requirements-dev.txt
```

### Run Tests

```bash
pytest
```

### With Coverage

```bash
export COVERAGE_PROCESS_START=$(pwd)/.coveragerc
pytest --cov --cov-report=term-missing
coverage html
xdg-open htmlcov/index.html
```

### Subprocess Coverage Setup

At the top of `producer.py` and `consumer.py`:

```python
import os
if os.getenv("COVERAGE_PROCESS_START"):
    import coverage
    coverage.process_startup()
```

---

## 📂 Project Structure

```
kafka-python-demo/
├── producer.py          # Sends JSON messages to Apache Kafka
├── consumer.py          # Reads and parses both JSON and plain text messages
├── logger.py            # Logging configuration
├── requirements.txt     # Python dependencies
├── requirements-dev.txt # Python dependencies for development and testing
├── producer.Dockerfile  # Dockerfile for the producer service
├── consumer.Dockerfile  # Dockerfile for the consumer service
├── docker-compose.yml   # Docker Compose configuration for running the entire stack
├── tests/
├── .gitignore           # Python cache and venv exclusions
└── README.md            # Project overview and usage instructions
```

---

## 📌 Notes

- Topic name is hardcoded as `test-topic` in both scripts.
- You can edit the scripts to change topic names or message structures.
- This setup is great for local experimentation or as a starting point for more advanced Apache Kafka integrations.

---

## 🐳 Docker Setup

This project includes Docker support to run the entire stack (Kafka, producer, and consumer) in containers.

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Running with Docker Compose

1. Build and start all services:

    ```shell
    docker-compose up -d
    ```

    This will start:
    - Kafka (using the official Apache Kafka image in KRaft mode without Zookeeper)
    - Producer (which will start sending messages immediately)
    - Consumer (which will start consuming messages immediately)

    The Dockerfiles for the producer and consumer automatically modify the Python scripts to use environment variables for Kafka connection, making them ready to connect to the Kafka service in the Docker network.

2. View logs from the consumer:

    ```shell
    docker logs -f kafka-consumer
    ```

3. View logs from the producer:

    ```shell
    docker logs -f kafka-producer
    ```

### Customizing the Consumer

You can customize the consumer by modifying the `command` section in the `docker-compose.yml` file:

```yaml
consumer:
  # ... other settings ...
  command: ["--group-id", "demo-group"]
```

Available options:
- `--group-id` or `-g`: Set a consumer group ID
- `--event-type` or `-e`: Filter by event type

### Stopping the Services

To stop all services:

```shell
docker-compose down
```

## 🔗 Links

- [Apache Kafka (Official)](https://kafka.apache.org/)
- [Kafka Quickstart Guide](https://kafka.apache.org/quickstart)
- [Kafka Docker Image (Official)](https://hub.docker.com/r/apache/kafka)
- [Kafka Python Client – kafka-python (GitHub)](https://github.com/dpkp/kafka-python)
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

## 🧪 Running Tests & Coverage

This project uses [pytest](https://docs.pytest.org/) and [testcontainers](https://pypi.org/project/testcontainers/) for integration testing, along with [coverage.py](https://coverage.readthedocs.io/) to track test coverage — including subprocesses.

### ✅ Requirements

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

### ▶️ Run All Tests

Run all tests (including those that spin up a Kafka container):

```bash
pytest
```

### 🧪 Run Integration Test Manually

You can run the integration test that uses `testcontainers` with Kafka:

```bash
pytest tests/test_kafka_integration.py
```

### ⚙️ Running Tests With Coverage (subprocess-safe)

To enable coverage tracking for both main tests and subprocesses:

#### 1. Export the coverage config path:

```bash
export COVERAGE_PROCESS_START=$(pwd)/.coveragerc
```

#### 2. Run tests with coverage:

```bash
pytest --cov --cov-report=term-missing
```

#### 3. Generate an HTML coverage report (optional):

```bash
coverage html
xdg-open htmlcov/index.html  # or open htmlcov/index.html manually
```

### 🧠 Subprocess Coverage Reminder

To properly collect coverage from subprocesses (like `subprocess.run(["python", "consumer.py"])`):

- Add this to the top of any script (like `producer.py`, `consumer.py`):

```python
import os
if os.getenv("COVERAGE_PROCESS_START"):
    import coverage
    coverage.process_startup()
```

---

## 🧾 About TemplateTasks

TemplateTasks is a personal software development initiative by Vadim Starichkov, focused on sharing open-source libraries, services, and technical demos.

It operates independently and outside the scope of any employment.

All code is released under permissive open-source licenses. The legal structure may evolve as the project grows.

## 📜 License & Attribution

This project is licensed under the **MIT License** - see the [LICENSE](https://github.com/starichkov/kafka-python-demo/blob/main/LICENSE.md) file for details.

### Using This Project?

If you use this code in your own projects, attribution is required under the MIT License:

```
Based on kafka-python-demo by Vadim Starichkov, TemplateTasks

https://github.com/starichkov/kafka-python-demo
```

**Copyright © 2025 Vadim Starichkov, TemplateTasks**
