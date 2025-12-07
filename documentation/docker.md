## 🐳 Docker Setup

This project includes Docker support to run the entire stack (Kafka, producer, and consumer) in containers.

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Running with Docker Compose

1. Build and start all services:

    ```shell
    docker compose up -d
    ```

    This will start:
    - Kafka (using the official Apache Kafka image in KRaft mode without Zookeeper)
    - Producer (which will start sending messages immediately)
    - Consumer (which will start consuming messages immediately)

    The Dockerfiles and docker-compose use environment variables for Kafka connection, making them ready to connect to the Kafka service in the Docker network.

2. Use a custom topic (optional):

    You can override the topic used by producer and consumer by setting `KAFKA_TOPIC` before running Compose:

    ```shell
    KAFKA_TOPIC=my-topic docker compose up -d
    ```

    Or create a `.env` file in the project root:

    ```env
    KAFKA_TOPIC=my-topic
    ```

    Then run:

    ```shell
    docker compose up -d
    ```

3. Switch producer payload format (JSON ⇄ Protobuf):

    The producer supports multiple formats. Default is JSON; set `MESSAGE_FORMAT=protobuf` to switch.

    Important: If the producer container is already running, you must recreate it for the new environment value to take effect.

    Examples:

    ```shell
    # Start stack with Protobuf
    MESSAGE_FORMAT=protobuf docker compose up -d

    # If the producer was previously running in JSON, force a recreate
    MESSAGE_FORMAT=protobuf docker compose up -d --force-recreate

    # Or tear down first, then start again
    docker compose down -v --remove-orphans
    MESSAGE_FORMAT=protobuf docker compose up -d
    ```

    You can confirm the active format from producer logs; on startup it logs the resolved format and content-type, e.g.:

    ```
    Producer starting with format=protobuf, content-type=application/x-protobuf
    ```

4. View logs from the consumer:

    ```shell
    docker logs -f kafka-consumer
    ```

5. View logs from the producer:

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

### Troubleshooting

- Seeing "✅ JSON (.. )" in consumer logs even when using Protobuf?
  This label reflects that the consumer parsed the payload into a dict, not the on-wire format. When using Protobuf, the consumer parses it and still logs with the JSON prefix. Check the producer startup line for the actual on-wire format and the consumer’s wire annotation suffix.

- Wire format annotation in consumer logs
  Each message line now ends with a suffix indicating the detected wire format: `[wire=protobuf]`, `[wire=json]`, `[wire=text]`, or `[wire=unknown]`.
  Examples:
  - `✅ JSON (note_created) | key=note_created | partition=0 | offset=1 → {...} [wire=protobuf]`
  - `📦 Plain | key=plain | partition=0 | offset=42 → hello [wire=text]`

- Changed `MESSAGE_FORMAT` but output didn’t change?
  Recreate the producer container with `--force-recreate`, or run `docker compose down` followed by `docker compose up -d`.

### Stopping the Services

To stop all services:

```shell
docker compose down
```
