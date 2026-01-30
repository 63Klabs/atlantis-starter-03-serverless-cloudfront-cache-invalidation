# Test Mock Serialization Fix - Design

## Solution Overview
Fix the JSON serialization issue by creating proper Lambda context fixtures and improving the logger's error handling for non-serializable objects.

## Design Decisions

### Option 1: Create Realistic Lambda Context Fixtures (CHOSEN)
**Pros:**
- Tests more accurately reflect production behavior
- Reusable across all test files
- No changes to production code
- Easy to maintain

**Cons:**
- Requires updating existing tests
- Need to create fixture in conftest.py

### Option 2: Modify Logger to Handle Mock Objects
**Pros:**
- Minimal test changes
- Centralized fix

**Cons:**
- Adds complexity to production code
- May hide real serialization issues
- Not a clean separation of concerns

### Option 3: Skip Logging in Tests
**Pros:**
- Quick fix
- No production code changes

**Cons:**
- Reduces test coverage
- Doesn't test logging behavior
- May miss logging-related bugs

## Implementation Design

### 1. Lambda Context Fixture
Create a reusable Lambda context fixture in `tests/conftest.py`:

```python
class MockLambdaContext:
    """Mock Lambda context for testing."""
    
    def __init__(self, 
                 function_name='test-function',
                 function_version='$LATEST',
                 memory_limit_in_mb=128,
                 aws_request_id='test-request-id',
                 remaining_time_ms=300000):
        self.function_name = function_name
        self.function_version = function_version
        self.memory_limit_in_mb = memory_limit_in_mb
        self.aws_request_id = aws_request_id
        self._remaining_time_ms = remaining_time_ms
    
    def get_remaining_time_in_millis(self):
        """Return remaining execution time in milliseconds."""
        return self._remaining_time_ms
```

### 2. Update Failing Property Test
Replace `Mock()` context with `MockLambdaContext()`:

```python
# Before
context = Mock()
context.aws_request_id = 'test-request-id'

# After
context = MockLambdaContext(aws_request_id='test-request-id')
```

### 3. Logger Enhancement (Optional Safety Net)
Add try-except in logger to handle serialization failures gracefully:

```python
def format(self, record: logging.LogRecord) -> str:
    """Format log record as JSON with error handling."""
    try:
        # ... existing code ...
        return json.dumps(log_data, cls=DateTimeEncoder)
    except (TypeError, ValueError) as e:
        # Fallback to string representation if JSON serialization fails
        log_data['_serialization_error'] = str(e)
        log_data['message'] = str(record.getMessage())
        # Remove problematic fields
        if 'extra_fields' in log_data:
            log_data['extra_fields'] = '<non-serializable>'
        return json.dumps(log_data)
```

## Testing Strategy

### Unit Tests
- Test MockLambdaContext fixture provides all required attributes
- Test MockLambdaContext methods return correct types
- Test logger handles serialization errors gracefully

### Property Tests
- Update existing failing property test to use MockLambdaContext
- Verify property tests pass with new fixture
- Ensure tests complete within time limits

### Integration Tests
- No changes required (integration tests don't use mocks)

## Correctness Properties

### Property 1: Mock Context Completeness
**Statement:** For any Lambda handler invocation in tests, the mock context must provide all attributes accessed by the handler.

**Test Strategy:**
- Unit test verifying all context attributes exist
- Property test verifying handler doesn't fail with mock context

### Property 2: Logger Resilience
**Statement:** For any log message, the logger must not crash the application due to serialization failures.

**Test Strategy:**
- Unit test with intentionally non-serializable objects
- Verify logger returns valid JSON or fallback string

## Files to Modify

1. **tests/conftest.py**
   - Add MockLambdaContext class
   - Add pytest fixture for lambda_context

2. **tests/property/test_properties_path_consolidation.py**
   - Replace Mock() with MockLambdaContext()
   - Line ~1720

3. **layers/common/python/common/logger.py** (Optional)
   - Add error handling in JSONFormatter.format()
   - Add fallback serialization

## Rollout Plan

1. Create MockLambdaContext fixture in conftest.py
2. Update failing property test
3. Run tests locally to verify fix
4. (Optional) Add logger error handling
5. Commit and test in CI/CD pipeline

## Backward Compatibility
- Existing tests using Mock() will continue to work
- New fixture is opt-in for tests that need it
- No breaking changes to production code
