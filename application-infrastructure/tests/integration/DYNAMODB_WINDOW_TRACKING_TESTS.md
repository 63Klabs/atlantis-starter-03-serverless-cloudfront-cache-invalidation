# DynamoDB Window Tracking Integration Tests

## Overview

This document describes the integration tests for the DynamoDB window tracking mechanism, which manages aggregation windows for the CloudFront invalidation service.

## Test File

`test_dynamodb_window_tracking.py`

## Requirements Tested

- **4.1**: Window creation on first event
- **4.2**: Duplicate schedule prevention
- **4.4**: Window closure after processing

## Test Classes

### TestWindowCreation

Tests the creation of aggregation windows when the first event is processed.

**Tests:**
1. `test_create_window_on_first_event`
   - Verifies no active window exists initially
   - Creates a new window
   - Verifies window has correct attributes (windowId, status, scheduleArn, timestamps, TTL)
   - Validates timestamp calculations

2. `test_window_attributes_are_correct`
   - Verifies all required attributes exist
   - Validates attribute types (string, int)
   - Checks attribute values match expectations

### TestDuplicateSchedulePrevention

Tests that subsequent events within an active window do not create duplicate schedules.

**Tests:**
1. `test_prevent_duplicate_schedule_creation`
   - Creates first window (succeeds)
   - Attempts to create second window (fails)
   - Verifies original window remains unchanged
   - Validates schedule ARN and timestamps are preserved

2. `test_multiple_concurrent_create_attempts`
   - Simulates race condition with multiple concurrent create attempts
   - Verifies exactly one creation succeeds
   - Validates only one window exists
   - Checks schedule ARN matches first successful creation

### TestWindowClosure

Tests the window closure mechanism after processing completes.

**Tests:**
1. `test_close_window_after_processing`
   - Creates an active window
   - Closes the window
   - Verifies window is no longer active
   - Validates window status changed to 'closed'
   - Confirms other attributes remain unchanged

2. `test_close_nonexistent_window`
   - Attempts to close a window that doesn't exist
   - Verifies operation returns False gracefully

3. `test_create_new_window_after_closure`
   - Creates first window
   - Closes the window
   - Creates second window (should succeed)
   - Verifies new window has later timestamps
   - Validates complete window lifecycle

### TestTTLCleanup

Tests the TTL (Time To Live) mechanism for automatic cleanup of old window records.

**Tests:**
1. `test_ttl_attribute_is_set`
   - Creates a window
   - Verifies TTL attribute exists
   - Validates TTL calculation (windowEndTime + buffer)
   - Confirms TTL is in the future

2. `test_ttl_configuration_on_table`
   - Checks DynamoDB table has TTL enabled
   - Verifies TTL attribute name is 'ttl'
   - Validates TTL status is ENABLED or ENABLING

3. `test_closed_window_has_ttl`
   - Creates and closes a window
   - Verifies TTL persists after closure
   - Validates TTL value doesn't change

### TestWindowTrackingEdgeCases

Tests edge cases and boundary conditions.

**Tests:**
1. `test_check_active_window_when_none_exists`
   - Verifies check_active_window returns None when no window exists

2. `test_window_id_is_always_current`
   - Validates windowId is always the fixed value 'current'

3. `test_window_timestamps_are_monotonic`
   - Creates multiple windows over time
   - Verifies timestamps are monotonically increasing

## Test Fixtures

### `dynamodb_client`
- Scope: module
- Creates boto3 DynamoDB client for low-level operations

### `dynamodb_resource`
- Scope: module
- Creates boto3 DynamoDB resource for high-level operations

### `test_config`
- Scope: module
- Loads TRACKING_TABLE from environment variables
- Skips tests if configuration is missing

### `clean_window_state`
- Scope: function
- Ensures clean state before and after each test
- Deletes any existing window before test runs
- Cleans up window after test completes

## Running the Tests

### Prerequisites

1. Deployed CloudFormation stack with DynamoDB table
2. AWS credentials configured
3. Environment variables set:
   ```bash
   export RUN_INTEGRATION_TESTS=1
   export TRACKING_TABLE="your-prefix-project-stage-WindowTracking"
   ```

### Run All Window Tracking Tests

```bash
cd application-infrastructure
pytest tests/integration/test_dynamodb_window_tracking.py -v
```

### Run Specific Test Classes

```bash
# Window creation tests
pytest tests/integration/test_dynamodb_window_tracking.py::TestWindowCreation -v

# Duplicate prevention tests
pytest tests/integration/test_dynamodb_window_tracking.py::TestDuplicateSchedulePrevention -v

# Window closure tests
pytest tests/integration/test_dynamodb_window_tracking.py::TestWindowClosure -v

# TTL cleanup tests
pytest src/tests/integration/test_dynamodb_window_tracking.py::TestTTLCleanup -v

# Edge case tests
pytest src/tests/integration/test_dynamodb_window_tracking.py::TestWindowTrackingEdgeCases -v
```

### Run Specific Tests

```bash
# Test window creation
pytest src/tests/integration/test_dynamodb_window_tracking.py::TestWindowCreation::test_create_window_on_first_event -v

# Test duplicate prevention
pytest src/tests/integration/test_dynamodb_window_tracking.py::TestDuplicateSchedulePrevention::test_prevent_duplicate_schedule_creation -v

# Test window closure
pytest src/tests/integration/test_dynamodb_window_tracking.py::TestWindowClosure::test_close_window_after_processing -v
```

## Expected Behavior

### Successful Test Run

All tests should pass when:
- DynamoDB table exists and is accessible
- IAM permissions allow PutItem, GetItem, UpdateItem, DeleteItem, DescribeTimeToLive
- TTL is enabled on the table with attribute name 'ttl'
- No other processes are interfering with the 'current' window

### Common Failures

1. **Missing TRACKING_TABLE**: Tests are skipped
   - Solution: Set TRACKING_TABLE environment variable

2. **Permission Denied**: Tests fail with AccessDenied errors
   - Solution: Verify IAM permissions for DynamoDB operations

3. **TTL Not Enabled**: TTL tests fail
   - Solution: Enable TTL on the table with attribute name 'ttl'

4. **Concurrent Access**: Race condition tests may occasionally fail
   - Solution: This is expected behavior; retry the test

## Test Coverage

These integration tests verify:

✅ Window creation with correct attributes  
✅ Conditional write prevents duplicate windows  
✅ Active window detection works correctly  
✅ Window closure updates status  
✅ TTL is set and persists  
✅ Window lifecycle (create → close → create new)  
✅ Race condition handling  
✅ Edge cases and error conditions  

## Notes

### TTL Cleanup Timing

The tests verify that the TTL attribute is set correctly, but they cannot test the actual deletion by DynamoDB because:
- TTL cleanup is asynchronous
- Deletion may take up to 48 hours
- Exact timing is not guaranteed

The tests confirm:
- TTL attribute exists
- TTL value is calculated correctly
- TTL is enabled on the table

### Test Isolation

Each test uses the `clean_window_state` fixture to ensure:
- No leftover state from previous tests
- Clean environment for each test
- Proper cleanup after test completion

### Performance

These tests interact with real DynamoDB and may take several seconds to complete due to:
- Network latency
- DynamoDB consistency model
- Sleep delays for state propagation

## Troubleshooting

### Tests are Skipped

Check:
1. `RUN_INTEGRATION_TESTS=1` is set
2. `TRACKING_TABLE` environment variable is set
3. AWS credentials are configured

### Tests Fail with ConditionalCheckFailedException

This may indicate:
1. Another process is creating windows
2. Previous test didn't clean up properly
3. Manual intervention needed to delete the 'current' window

Solution:
```bash
aws dynamodb delete-item \
  --table-name $TRACKING_TABLE \
  --key '{"windowId": {"S": "current"}}'
```

### Tests Fail with ResourceNotFoundException

The DynamoDB table doesn't exist or the name is incorrect.

Solution:
1. Verify the stack is deployed
2. Check the table name in CloudFormation outputs
3. Update TRACKING_TABLE environment variable

### TTL Tests Fail

The table may not have TTL enabled.

Solution:
```bash
aws dynamodb update-time-to-live \
  --table-name $TRACKING_TABLE \
  --time-to-live-specification "Enabled=true, AttributeName=ttl"
```

## Cost Considerations

These integration tests:
- Perform DynamoDB read/write operations (minimal cost)
- Use on-demand pricing (no provisioned capacity)
- Clean up test data automatically
- Should cost less than $0.01 per test run

## Cleanup

After running tests, the `clean_window_state` fixture automatically cleans up. If manual cleanup is needed:

```bash
# Delete the current window
aws dynamodb delete-item \
  --table-name $TRACKING_TABLE \
  --key '{"windowId": {"S": "current"}}'

# Verify deletion
aws dynamodb get-item \
  --table-name $TRACKING_TABLE \
  --key '{"windowId": {"S": "current"}}'
```
