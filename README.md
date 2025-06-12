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

The `producer.py` script sends a few JSON messages to the topic `test-topic`:

```shell
python producer.py
```

Example output:

```
Sent: {'id': 0, 'text': 'Message 0'}
Sent: {'id': 1, 'text': 'Message 1'}
...
```

---

### 3. Run the Consumer

The `consumer.py` script reads messages from the topic and parses them. It will:

- Parse and display JSON messages as dictionaries
- Fall back to plain text for non-JSON messages

Run it with:

```shell
python consumer.py
```

Example output:

```
Polyglot consumer listening...

📦 Plain: First message
📦 Plain: Second message
📦 Plain: Tired, shutting down.
✅ JSON: {'id': 0, 'text': 'Message 0'}
✅ JSON: {'id': 1, 'text': 'Message 1'}
✅ JSON: {'id': 2, 'text': 'Message 2'}
✅ JSON: {'id': 3, 'text': 'Message 3'}
✅ JSON: {'id': 4, 'text': 'Message 4'}
```

Use `Ctrl+C` to stop the consumer gracefully.

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
