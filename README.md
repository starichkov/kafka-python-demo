[![Author](https://img.shields.io/badge/Author-Vadim%20Starichkov-blue?style=for-the-badge)](https://github.com/starichkov)
[![GitHub License](https://img.shields.io/github/license/starichkov/kafka-python-demo?style=for-the-badge)](https://github.com/starichkov/kafka-python-demo/blob/main/LICENSE.md)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/starichkov/kafka-python-demo/python.yml?style=for-the-badge)](https://github.com/starichkov/kafka-python-demo/actions/workflows/python.yml)
[![Codecov](https://img.shields.io/codecov/c/github/starichkov/kafka-python-demo?style=for-the-badge)](https://codecov.io/gh/starichkov/kafka-python-demo)

# Apache Kafka Python Demo

## Overview

A minimal Apache Kafka demo using Python featuring:
- A multi-format `producer.py` (JSON by default; Protobuf via env)
- A **format-tolerant** `consumer.py` supporting JSON, Protobuf & plain text
- Partition-awareness, message keying, and consumer group support
- Integration testing via `Testcontainers`
- GitHub Actions & Codecov integration

It’s designed to simulate a polyglot messaging environment, where different systems or services might produce data in different formats to the same Apache Kafka topic.

---

## Requirements

- Python 3.10+
- Docker & Docker Compose (for container-based setup) - more details could be found in the [separate section](documentation/docker.md).
- Apache Kafka (external or Dockerized)

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the Demo

### 1. Start Apache Kafka

You can start Apache Kafka using Docker. For example:

```shell
docker run -d --name kafka-391 \
  -p 9092:9092 \
  apache/kafka:3.9.1
```

More information about helper scripts Kafka provides could be found in the [separate section](documentation/kafka.md).

### Run Producer

```bash
python producer.py
```

Produces random events (`note_created`, `note_updated`, `note_deleted`) with message keys for partitioning.

Formats:
- JSON (default)
- Protobuf (enable via `MESSAGE_FORMAT=protobuf`)

Examples:

```bash
# JSON (default)
python producer.py

# Protobuf
MESSAGE_FORMAT=protobuf python producer.py
```

### Run Consumer

```bash
python consumer.py                   # All events
python consumer.py --event-type X   # Filtered by event_type
python consumer.py --group-id my-group
```

Displays event type, partition, and offset info. The consumer detects the payload format using the Kafka `content-type` header sent by the producer and falls back to JSON-or-plain-text when the header is missing.

Log annotation:
- Each consumed message line includes a suffix indicating the wire format detected: `[wire=protobuf]`, `[wire=json]`, `[wire=text]`, or `[wire=unknown]`.
- Example:
  - `✅ JSON (note_created) | key=note_created | partition=0 | offset=1 → {...} [wire=protobuf]`
  - `📦 Plain | key=plain | partition=0 | offset=42 → hello [wire=text]`
  
Note: The `✅ JSON (...)` prefix reflects that the payload was parsed into a dict (even for Protobuf). The `[wire=...]` suffix shows the on-wire format.

---

### Message Keys and Partitions

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

### Consumer Groups and Partition Rebalancing

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

## Running Tests & Coverage

Details could be found in the [separate section](documentation/tests.md).

Additionally, you can run a local Docker Compose smoke test that mirrors the CI job:

```
scripts/compose_smoke_test.sh        # real run
scripts/compose_smoke_test.sh --dry-run
```

---

## Project Structure

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

## Notes

- Topic name is configurable via environment variable `KAFKA_TOPIC` (default: `notes-topic`).
- You can edit the scripts to change topic names or message structures.
- This setup is great for local experimentation or as a starting point for more advanced Apache Kafka integrations.

### Configuration

- `KAFKA_BOOTSTRAP_SERVERS` — Kafka broker(s), default: `localhost:9092`
- `KAFKA_TOPIC` — topic to produce/consume, default: `notes-topic`
- `MESSAGE_FORMAT` — producer payload format: `json` (default) or `protobuf`

Examples:

```bash
# Run locally with a custom topic
export KAFKA_TOPIC=my-topic
python producer.py
python consumer.py

# Using Docker Compose (host env is picked up by compose)
KAFKA_TOPIC=my-topic docker compose up -d

# Switch producer to Protobuf in Docker Compose
MESSAGE_FORMAT=protobuf docker compose up -d
```

---

## Links

- [Status of Python versions](https://devguide.python.org/versions/)
- [Apache Kafka (Official)](https://kafka.apache.org/)
- [Kafka Quickstart Guide](https://kafka.apache.org/quickstart)
- [Kafka Docker Image (Official)](https://hub.docker.com/r/apache/kafka)
- [Kafka Python Client – kafka-python (GitHub)](https://github.com/dpkp/kafka-python)
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

## About TemplateTasks

TemplateTasks is a personal software development initiative by Vadim Starichkov, focused on sharing open-source libraries, services, and technical demos.

It operates independently and outside the scope of any employment.

All code is released under permissive open-source licenses. The legal structure may evolve as the project grows.

## License & Attribution

This project is licensed under the **MIT License** - see the [LICENSE](https://github.com/starichkov/kafka-python-demo/blob/main/LICENSE.md) file for details.

### Using This Project?

If you use this code in your own projects, attribution is required under the MIT License:

```
Based on kafka-python-demo by Vadim Starichkov, TemplateTasks

https://github.com/starichkov/kafka-python-demo
```

**Copyright © 2026 Vadim Starichkov, TemplateTasks**
