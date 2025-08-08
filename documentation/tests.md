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
pytest tests/test_kafka_integration.py
```

### ⚙️ Running Tests With Coverage (subprocess-safe)

To enable coverage tracking for both main tests and subprocesses:

#### 1. Export the coverage config path:

```bash
export COVERAGE_PROCESS_START=$(pwd)/.coveragerc
```

#### 2. Run tests with coverage:

```bash
pytest --cov --cov-report=term-missing
```

#### 3. Generate an HTML coverage report (optional):

```bash
coverage html
xdg-open htmlcov/index.html  # or open htmlcov/index.html manually
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
