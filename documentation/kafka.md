### Start Apache Kafka

You can start Apache Kafka using Docker. For example:

```shell
docker run -d --name kafka-391 \
  -p 9092:9092 \
  apache/kafka:3.9.1
```

Or use another Apache Kafka image you prefer. Ensure port `9092` is available.

Connect to the container:

```shell
docker exec -it kafka-391 bash
```

Proceed to the directory with scripts:

```shell
cd /opt/kafka/bin
```

And create the first topic to produce messages to:

```shell
./kafka-topics.sh --create \
  --topic test-topic \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

Now run producer scripts and type several messages into it:

```shell
./kafka-console-producer.sh \
  --topic test-topic \
  --bootstrap-server localhost:9092
```

for example:

```
>First message
>Second message
>Tired, shutting down.
```

Let's check messages by running a consumer script:

```shell
./kafka-console-consumer.sh \
  --topic test-topic \
  --from-beginning \
  --bootstrap-server localhost:9092
```

You should be able to see all your messages:

```
First message
Second message
Tired, shutting down.
```
