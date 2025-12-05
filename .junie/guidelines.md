# Junie Guidelines: Project Overview

Last updated: 2025-11-07 22:39 (local)

## What this repository is
A minimal Apache Kafka demo using Python. It showcases a JSON-producing producer, a format-tolerant consumer (JSON and plain text), partition awareness via message keys, consumer groups, integration tests with Testcontainers, and CI with GitHub Actions + Codecov.

## Key components
- producer.py
  - Sends JSON messages to a Kafka topic.
  - Uses the event_type as the Kafka key (partitioning by key, preserves per-key ordering).
  - Environment variables:
    - KAFKA_BOOTSTRAP_SERVERS (default: localhost:9092)
    - KAFKA_TOPIC (default: notes-topic)
  - Event types used: note_created, note_updated, note_deleted.

- consumer.py
  - Consumes messages from Kafka; parses JSON and falls back to plain text display if parsing fails.
  - CLI options:
    - --event-type X (filter messages by event_type)
    - --group-id NAME (join a consumer group to observe partition assignment and rebalances)
  - Prints key, partition, and offset for each message.

- logger.py
  - Centralized logging configuration used by producer/consumer.

- tests/
  - tests/test_integration.py: Integration tests powered by Testcontainers for Kafka.
  - run_tests_with_coverage.sh: Runs tests with coverage and generates HTML report under htmlcov/.

- Docker/Compose
  - producer.Dockerfile, consumer.Dockerfile: Container images for each service.
  - docker-compose.yml: Orchestrates local stack (Kafka, producer, consumer where applicable).

- CI/CD
  - .github/workflows/python.yml: Lint/Test workflow, publishes coverage to Codecov.

- Documentation
  - documentation/docker.md — notes on Docker usage in this project
  - documentation/kafka.md — Kafka helper scripts and tips
  - documentation/python.md — Python-related notes
  - documentation/tests.md — how to run tests and read coverage
  - documentation/improvements/* — ideas and recommendations

## Quickstart
1) Start Kafka (example):
```
docker run -d --name kafka-391 -p 9092:9092 apache/kafka:3.9.1
```

2) Install Python deps:
```
pip install -r requirements.txt
```

3) Run producer:
```
python producer.py
```

4) Run consumer:
```
python consumer.py                    # all events
python consumer.py --event-type X     # filter by event_type
python consumer.py --group-id demo    # observe consumer group behavior
```

## Behavior highlights
- Key-based partitioning: producer uses event_type as the Kafka key. Kafka guarantees ordering per key, not even distribution across partitions. With a small key set, some partitions may receive no messages.
- Consumer groups: run multiple consumers with the same --group-id to see partition rebalancing and assignment.

## Testing & coverage
- Dev dependencies: requirements-dev.txt
- Run tests with coverage:
```
./run_tests_with_coverage.sh
```
- HTML report is written to htmlcov/index.html.

## Configuration defaults
- Topic name: notes-topic (override via KAFKA_TOPIC)
- Bootstrap servers: localhost:9092 (override via KAFKA_BOOTSTRAP_SERVERS)
- Event types: note_created | note_updated | note_deleted

## Troubleshooting tips
- Ensure Kafka is reachable at KAFKA_BOOTSTRAP_SERVERS.
- If you see uneven partition usage, this is expected due to the small number of keys.
- For round-robin distribution, remove the key in producer (not default).

## Pointers
- README.md: comprehensive project overview and usage details
- documentation/ directory: deep-dive notes (Kafka, Docker, testing)

---
This guide is intended to give Junie and other contributors a fast, accurate mental model of the repo to speed up future tasks.
