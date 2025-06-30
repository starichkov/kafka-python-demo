FROM python:3.12.11-alpine3.22

WORKDIR /app

COPY requirements.txt .
# Install dependencies for building Python packages
RUN apk add --no-cache build-base
RUN pip install --no-cache-dir -r requirements.txt

COPY logger.py .
COPY consumer.py .

# Set environment variable for Kafka connection
ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Modify the consumer.py to use the environment variable
RUN sed -i "s/'bootstrap_servers': .*/'bootstrap_servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),/" consumer.py

# Add import os at the top of the file
RUN sed -i '1s/^/import os\n/' consumer.py

# Command to run the consumer
# The entrypoint allows passing additional arguments to the consumer
ENTRYPOINT ["python", "-u", "consumer.py"]
