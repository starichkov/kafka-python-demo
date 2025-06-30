FROM python:3.12.11-alpine3.22

WORKDIR /app

COPY requirements.txt .
# Install dependencies for building Python packages
RUN apk add --no-cache build-base
RUN pip install --no-cache-dir -r requirements.txt

COPY logger.py .
COPY consumer.py .

# Set environment variables for Kafka connection
ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092
ENV KAFKA_TOPIC=test-topic

# Command to run the consumer
# The entrypoint allows passing additional arguments to the consumer
ENTRYPOINT ["python", "-u", "consumer.py"]
