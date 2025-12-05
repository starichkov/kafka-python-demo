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
docker compose down
```
