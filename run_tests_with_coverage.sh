#!/bin/bash
# Enable coverage for subprocesses
export COVERAGE_PROCESS_START=$(pwd)/.coveragerc

# Argument parsing
KAFKA_VERSION_ARG=${1:-"4.2"}

case $KAFKA_VERSION_ARG in
    "3.9")
        DEFAULT_IMAGE="confluentinc/cp-kafka:7.9.8"
        ;;
    "4.2")
        DEFAULT_IMAGE="confluentinc/cp-kafka:8.2.2"
        ;;
    *)
        # If the argument looks like an image name (contains : or /), use it directly
        if [[ $KAFKA_VERSION_ARG == *":"* || $KAFKA_VERSION_ARG == *"/"* ]]; then
            DEFAULT_IMAGE=$KAFKA_VERSION_ARG
            KAFKA_VERSION_ARG="custom"
        else
            echo "⚠️  Unknown Kafka version: $KAFKA_VERSION_ARG. Defaulting to 4.2"
            KAFKA_VERSION_ARG="4.2"
            DEFAULT_IMAGE="confluentinc/cp-kafka:8.2.2"
        fi
        ;;
esac

# Use KAFKA_TEST_IMAGE if set, otherwise use the version-based default
export KAFKA_TEST_IMAGE=${KAFKA_TEST_IMAGE:-$DEFAULT_IMAGE}

rm -rf htmlcov/
rm -f .coverage
rm -f .coverage.*

echo "🚀 Running tests for Kafka $KAFKA_VERSION_ARG (Image: $KAFKA_TEST_IMAGE)"

pytest --cov --cov-report=term-missing
EXIT_CODE=$?

coverage html
echo "📊 Coverage report generated in htmlcov/index.html"

exit $EXIT_CODE