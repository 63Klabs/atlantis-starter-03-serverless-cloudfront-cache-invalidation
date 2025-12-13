# Test Directory Structure Analysis

## Current Directory Structure

```
application-infrastructure/src/tests/
├── __init__.py
├── integration/
│   ├── __init__.py
│   ├── DLQ_IMPLEMENTATION_SUMMARY.md
│   ├── DLQ_TESTS.md
│   ├── DYNAMODB_WINDOW_TRACKING_TESTS.md
│   ├── IMPLEMENTATION_SUMMARY.md
│   ├── README.md
│   ├── TESTING_GUIDE.md
│   ├── run_dlq_tests.sh
│   ├── run_integration_tests.sh
│   ├── test_dlq.py
│   ├── test_dynamodb_window_tracking.py
│   └── test_iam_permissions.py
├── property/
│   ├── __init__.py
│   ├── test_properties_distribution_discovery.py
│   ├── test_properties_grouping.py
│   ├── test_properties_handler.py
│   ├── test_properties_invalidation.py
│   ├── test_properties_logging.py
│   ├── test_properties_parsing.py
│   ├── test_properties_path_consolidation.py
│   ├── test_properties_processor_queuing.py
│   ├── test_properties_queuing.py
│   ├── test_properties_tag_validation.py
│   └── test_properties_window_tracking.py
└── unit/
    ├── __init__.py
    ├── test_ingestor_handler.py
    ├── test_logger.py
    ├── test_path_consolidator.py
    ├── test_path_validator.py
    ├── test_processor_handler.py
    ├── test_retry.py
    └── test_section_header_manager.py
```

## File Count Summary

- **Total test files**: 25 Python test files
- **Integration tests**: 3 Python files + 2 shell scripts + 6 documentation files
- **Property tests**: 11 Python files
- **Unit tests**: 7 Python files
- **Documentation files**: 6 markdown files
- **Shell scripts**: 2 executable scripts

## Import Pattern Analysis

### Current Import Patterns

All Python test files use the following pattern to add the src directory to the Python path:

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
```

**Breakdown by test type:**

1. **Unit tests** (`src/tests/unit/*.py`):
   - Path: `'../..'` (goes up 2 levels from unit/ to src/)
   - Example: `test_ingestor_handler.py` imports `from ingestor.handler import ...`

2. **Property tests** (`src/tests/property/*.py`):
   - Path: `'../..'` (goes up 2 levels from property/ to src/)
   - Example: `test_properties_handler.py` imports `from ingestor.handler import ...`

3. **Integration tests** (`src/tests/integration/*.py`):
   - Path: `'../../'` (goes up 2 levels from integration/ to src/)
   - Example: `test_dynamodb_window_tracking.py` imports `from ingestor.window_tracker import ...`

### Dependencies Imported

**Common application modules imported:**
- `ingestor.handler`
- `ingestor.event_parser`
- `ingestor.queue_client`
- `ingestor.window_tracker`
- `processor.handler`
- `processor.path_validator`
- `processor.path_consolidator`
- `common.logger`
- `common.retry`

**Testing framework dependencies:**
- `pytest` (unit and integration tests)
- `hypothesis` (property-based tests)
- `unittest.mock` (mocking)
- `boto3` and `moto` (AWS service mocking)

## Build Configuration Analysis

### Current buildspec.yml

The current build configuration:
- Installs dependencies from `application-infrastructure/src/requirements.txt` (which doesn't exist)
- No explicit test execution in the build pipeline
- Uses `application-infrastructure/requirements.txt` for dependencies

### Test Execution Scripts

Two shell scripts handle test execution:
1. `run_integration_tests.sh` - Sets up AWS environment and runs integration tests
2. `run_dlq_tests.sh` - Specialized script for DLQ integration tests

Both scripts:
- Change directory to `application-infrastructure/` root
- Run pytest with paths like `src/tests/integration/test_*.py`
- Expect to be run from the application-infrastructure directory

## Dependencies Analysis

### Current requirements.txt

```
boto3==1.35.36
botocore==1.35.36
pytest==8.3.3
pytest-mock==3.14.0
hypothesis==6.112.1
moto[all]==5.0.18
```

All test dependencies are currently in the main requirements.txt file.

## Import Path Updates Required

When moving from `src/tests/` to `tests/`, the sys.path.insert statements need to change:

**Current pattern:**
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
```

**New pattern (after restructure):**
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))
```

**Files requiring updates:** All 21 Python test files that contain sys.path.insert statements.

## Configuration Files Requiring Updates

1. **buildspec.yml**: Update any test-related paths and dependency installation
2. **Shell scripts**: Update pytest execution paths from `src/tests/` to `tests/`
3. **Documentation**: Update any references to test file locations

## Virtual Environment Requirements

For the new test virtual environment (`.venv-test`):
- Location: `application-infrastructure/tests/.venv-test/`
- Requirements file: `application-infrastructure/tests/requirements.txt`
- Should contain all current testing dependencies
- Separate from main application dependencies

## Summary

The restructuring involves:
- Moving 25 Python files + 6 documentation files + 2 shell scripts
- Updating 21 sys.path.insert statements
- Creating new virtual environment structure
- Updating build configuration
- Maintaining all existing test functionality