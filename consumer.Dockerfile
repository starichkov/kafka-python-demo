FROM python:3.13-alpine3.23

WORKDIR /app

COPY requirements.txt .
# Install dependencies for building Python packages
RUN apk add --no-cache build-base
RUN pip install --no-cache-dir -r requirements.txt

COPY logger.py .
COPY consumer.py .
COPY serialization ./serialization

# Allow overriding Kafka connection via build args or env at runtime
ARG KAFKA_BOOTSTRAP_SERVERS=kafka:9092
ARG KAFKA_TOPIC=test-topic
ENV KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS}
ENV KAFKA_TOPIC=${KAFKA_TOPIC}

# Create an unprivileged user and switch to it
RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app
USER app

ENTRYPOINT ["python", "-u", "consumer.py"]
