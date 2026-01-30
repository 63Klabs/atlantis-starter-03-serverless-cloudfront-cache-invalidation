# Test Mock Serialization Fix - Tasks

## Task List

- [x] 1. Create MockLambdaContext fixture
  - [x] 1.1 Add MockLambdaContext class to tests/conftest.py
  - [x] 1.2 Add pytest fixture for lambda_context
  - [x] 1.3 Add unit tests for MockLambdaContext

- [x] 2. Update failing property test
  - [x] 2.1 Replace Mock() with MockLambdaContext in test_properties_path_consolidation.py
  - [x] 2.2 Verify test passes locally
  - [x] 2.3 Check for other tests using Mock() for Lambda context

- [x] 3. Add logger error handling (optional safety net)
  - [x] 3.1 Add try-except in JSONFormatter.format()
  - [x] 3.2 Add unit tests for logger error handling
  - [x] 3.3 Verify logger doesn't crash on non-serializable objects

- [x] 4. Verify all tests pass
  - [x] 4.1 Run unit tests locally
  - [x] 4.2 Run property tests locally
  - [x] 4.3 Verify test execution time is acceptable

## Task Details

### 1.1 Add MockLambdaContext class to tests/conftest.py
Create a realistic Lambda context mock that provides all attributes and methods used by the handler.

**Implementation:**
- Add MockLambdaContext class with all required attributes
- Implement get_remaining_time_in_millis() method
- Make all attributes JSON serializable

### 1.2 Add pytest fixture for lambda_context
Create a pytest fixture that returns a MockLambdaContext instance.

**Implementation:**
- Add @pytest.fixture decorator
- Return MockLambdaContext with sensible defaults
- Allow customization via parameters

### 1.3 Add unit tests for MockLambdaContext
Verify the fixture works correctly.

**Implementation:**
- Test all attributes are present
- Test get_remaining_time_in_millis() returns integer
- Test context is JSON serializable

### 2.1 Replace Mock() with MockLambdaContext
Update the failing property test to use the new fixture.

**Location:** tests/property/test_properties_path_consolidation.py, line ~1720

**Implementation:**
- Import MockLambdaContext from conftest
- Replace `context = Mock()` with `context = MockLambdaContext()`
- Remove `context.aws_request_id = 'test-request-id'` (already set in constructor)

### 2.2 Verify test passes locally
Run the specific failing test to confirm the fix works.

**Command:**
```bash
cd application-infrastructure
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/layers/common/python"
python -m pytest tests/property/test_properties_path_consolidation.py::test_property_2_bucket_specific_sibling_threshold_usage -v
```

### 2.3 Check for other tests using Mock() for Lambda context
Search for other tests that might have the same issue.

**Command:**
```bash
grep -r "context = Mock()" tests/
```

### 3.1 Add try-except in JSONFormatter.format()
Add error handling to prevent crashes on serialization failures.

**Implementation:**
- Wrap json.dumps() in try-except
- Catch TypeError and ValueError
- Return fallback JSON with error message

### 3.2 Add unit tests for logger error handling
Verify logger handles non-serializable objects gracefully.

**Implementation:**
- Create test with Mock object in extra_fields
- Verify logger returns valid JSON
- Verify no exceptions are raised

### 4.1 Run unit tests locally
Verify all unit tests still pass.

**Command:**
```bash
cd application-infrastructure
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/layers/common/python"
python -m pytest tests/unit/ -v
```

### 4.2 Run property tests locally
Verify all property tests pass.

**Command:**
```bash
cd application-infrastructure
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/layers/common/python"
python -m pytest tests/property/ -v
```

### 4.3 Verify test execution time
Ensure tests complete within acceptable time limits.

**Acceptance Criteria:**
- Unit tests: < 5 seconds
- Property tests: < 10 seconds
- Total test suite: < 30 seconds
