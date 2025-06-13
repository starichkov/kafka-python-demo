[![Author](https://img.shields.io/badge/Author-Vadim%20Starichkov-blue?style=for-the-badge)](https://github.com/starichkov)
[![GitHub License](https://img.shields.io/github/license/starichkov/kafka-python-demo?style=for-the-badge)](https://github.com/starichkov/kafka-python-demo/blob/main/LICENSE.md)

# Apache Kafka Python Demo

A minimal Apache Kafka demo using Python to send and receive messages. This project includes:

- A producer that sends JSON messages
- A consumer that can handle both JSON and plain text messages

It’s designed to simulate a polyglot messaging environment, where different systems or services might produce data in different formats to the same Apache Kafka topic.

---

## 🧰 Requirements

- Python 3.7 or later
- A running Apache Kafka broker (e.g., via Docker)

To install dependencies:

```shell
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

Let's check messages by running consumer script:

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

---

### 2. Run the Producer

The `producer.py` script sends JSON messages to the topic `test-topic`. Each message includes an `event_type`, chosen randomly from:

- `note_created`
- `note_updated`
- `note_deleted`

```shell
python producer.py
```

Example output:

```
Sent: {'id': 0, 'event_type': 'note_deleted', 'text': 'Note event 0 of type note_deleted'}
Sent: {'id': 1, 'event_type': 'note_created', 'text': 'Note event 1 of type note_created'}
Sent: {'id': 2, 'event_type': 'note_deleted', 'text': 'Note event 2 of type note_deleted'}
...
```

---

### 3. Run the Consumer

The `consumer.py` script reads messages from the topic and parses them. It:

- Parses and displays JSON messages with structured output
- Falls back to plain text for non-JSON messages
- Accepts an optional `--event-type` argument to filter messages

Examples:

```bash
python consumer.py                             # consume all messages
python consumer.py --event-type note_created   # filter by event_type
```

Example output:

```
Polyglot consumer listening...

✅ JSON (note_deleted): {'id': 0, 'event_type': 'note_deleted', 'text': 'Note event 0 of type note_deleted'}
✅ JSON (note_created): {'id': 1, 'event_type': 'note_created', 'text': 'Note event 1 of type note_created'}
✅ JSON (note_deleted): {'id': 2, 'event_type': 'note_deleted', 'text': 'Note event 2 of type note_deleted'}
✅ JSON (note_updated): {'id': 3, 'event_type': 'note_updated', 'text': 'Note event 3 of type note_updated'}
```

Use `Ctrl+C` to stop the consumer gracefully.

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

## 📂 Project Structure

```
kafka-python-demo/
├── producer.py          # Sends JSON messages to Apache Kafka
├── consumer.py          # Reads and parses both JSON and plain text messages
├── requirements.txt     # Python dependencies
├── .gitignore           # Python cache and venv exclusions
└── README.md            # Project overview and usage instructions
```

---

## 📌 Notes

- Topic name is hardcoded as `test-topic` in both scripts.
- You can edit the scripts to change topic names or message structures.
- This setup is great for local experimentation or as a starting point for more advanced Apache Kafka integrations.

---

## 🔗 Links

- [Apache Kafka (Official)](https://kafka.apache.org/)
- [Kafka Quickstart Guide](https://kafka.apache.org/quickstart)
- [Kafka Docker Image (Official)](https://hub.docker.com/r/apache/kafka)
- [Kafka Python Client – kafka-python (GitHub)](https://github.com/dpkp/kafka-python)

---

## 📜 License & Attribution

This project is licensed under the **MIT License** - see the [LICENSE](https://github.com/starichkov/kafka-python-demo/blob/main/LICENSE.md) file for details.

### Using This Project?

If you use this code in your own projects, attribution is required under the MIT License:

```
Based on kafka-python-demo by Vadim Starichkov, TemplateTasks

https://github.com/starichkov/kafka-python-demo
```

**Copyright © 2025 Vadim Starichkov, TemplateTasks**
