FROM python:3.13.9-alpine3.22

WORKDIR /app

COPY requirements.txt .
# Install dependencies for building Python packages
RUN apk add --no-cache build-base
RUN pip install --no-cache-dir -r requirements.txt

COPY logger.py .
COPY producer.py .

# Set environment variables for Kafka connection
ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092
ENV KAFKA_TOPIC=test-topic

CMD ["python", "-u", "producer.py"]
