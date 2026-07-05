## 🧪 Running Tests & Coverage

This project uses [pytest](https://docs.pytest.org/) and [testcontainers](https://pypi.org/project/testcontainers/) for integration testing, along with [coverage.py](https://coverage.readthedocs.io/) to track test coverage — including subprocesses.

### ✅ Requirements

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

### ▶️ Run All Tests

Run all tests (including those that spin up a Kafka container):

```bash
pytest
```

### 🧪 Run Integration Test Manually

You can run the integration test that uses `testcontainers` with Kafka:

```bash
pytest tests/test_integration.py
```

### ⚙️ Running Tests With Coverage

The easiest way to run all tests with coverage is to use the provided helper script:

```bash
./run_tests_with_coverage.sh
```

This script will:
1. Clear previous coverage data and HTML report.
2. Run all tests with coverage enabled.
3. Generate a new HTML report in `htmlcov/index.html`.

#### Testing different Kafka versions

By default, the script runs tests against Kafka 4.2. You can specify the version as an argument:

```bash
# Test with Kafka 4.2 (default)
./run_tests_with_coverage.sh

# Test with Kafka 3.9
./run_tests_with_coverage.sh 3.9
```

Alternatively, you can specify a full Kafka image name or use the `KAFKA_TEST_IMAGE` environment variable:

```bash
# Using a custom image as an argument
./run_tests_with_coverage.sh confluentinc/cp-kafka:8.2.2

# Using environment variable
KAFKA_TEST_IMAGE=confluentinc/cp-kafka:7.9.8 ./run_tests_with_coverage.sh
```

### 🧠 Subprocess Coverage Reminder

To properly collect coverage from subprocesses (like `subprocess.run(["python", "consumer.py"])`):

- Add this to the top of any script (like `producer.py`, `consumer.py`):

```python
import os
if os.getenv("COVERAGE_PROCESS_START"):
    import coverage
    coverage.process_startup()
```
