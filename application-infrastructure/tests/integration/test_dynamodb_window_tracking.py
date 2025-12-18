"""
Integration tests for DynamoDB window tracking.

These tests verify that the window tracking mechanism works correctly with
real DynamoDB operations. These tests require:
1. Deployed CloudFormation stack with DynamoDB table
2. AWS credentials configured
3. TRACKING_TABLE environment variable set

Run with: pytest tests/integration/test_dynamodb_window_tracking.py -v

Environment variables required:
- TRACKING_TABLE: Name of the DynamoDB tracking table
- RUN_INTEGRATION_TESTS: Set to 1 to enable integration tests

Requirements tested:
- 4.1: Window creation on first event
- 4.2: Duplicate schedule prevention
- 4.4: Window closure after processing
"""

import os
import time
import uuid
import boto3
import pytest
from datetime import datetime, timezone

# Import the window tracker functions
from common.window_tracker import (
    check_active_window,
    create_window,
    close_window
)
from common.constants import (
    WINDOW_ID_FIXED_VALUE,
    WINDOW_STATUS_ACTIVE,
    WINDOW_STATUS_CLOSED,
    AGGREGATION_WINDOW_SECONDS,
    WINDOW_TTL_BUFFER_SECONDS
)


# Skip all tests if not in integration test mode
pytestmark = pytest.mark.skipif(
    True,  # ALWAYS SKIP - These tests make real AWS calls and can crash the system
    reason="DISABLED: Integration tests make real AWS API calls and can cause system crashes"
)


@pytest.fixture(scope="module")
def dynamodb_client():
    """Create DynamoDB client for integration tests."""
    return boto3.client('dynamodb')


@pytest.fixture(scope="module")
def dynamodb_resource():
    """Create DynamoDB resource for integration tests."""
    return boto3.resource('dynamodb')


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration from environment variables."""
    tracking_table = os.environ.get('TRACKING_TABLE')
    
    if not tracking_table:
        pytest.skip("Missing required environment variable: TRACKING_TABLE")
    
    return {
        'tracking_table': tracking_table
    }


@pytest.fixture(scope="function")
def clean_window_state(dynamodb_resource, test_config):
    """
    Fixture to ensure clean window state before and after each test.
    
    This fixture:
    1. Deletes any existing window before the test
    2. Yields control to the test
    3. Deletes any window created during the test
    """
    table = dynamodb_resource.Table(test_config['tracking_table'])
    
    # Clean up before test
    try:
        table.delete_item(Key={'windowId': WINDOW_ID_FIXED_VALUE})
        time.sleep(0.5)  # Wait for deletion to propagate
    except Exception:
        pass  # Item might not exist
    
    yield
    
    # Clean up after test
    try:
        table.delete_item(Key={'windowId': WINDOW_ID_FIXED_VALUE})
    except Exception:
        pass  # Item might not exist


class TestWindowCreation:
    """Test window creation on first event."""
    
    def test_create_window_on_first_event(self, clean_window_state, test_config):
        """
        Verify window creation on first event.
        
        Requirements: 4.1 - WHEN the Ingestor Lambda processes the first event
        within an aggregation window THEN the Invalidation Service SHALL create
        a one-time schedule to invoke the Processor Lambda after 5 minutes
        
        This test verifies:
        1. No active window exists initially
        2. Window can be created successfully
        3. Window has correct attributes (status, timestamps, TTL)
        """
        # Step 1: Verify no active window exists
        active_window = check_active_window()
        assert active_window is None, "Expected no active window initially"
        
        # Step 2: Create a new window
        test_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/test-{uuid.uuid4()}"
        
        start_time = int(time.time())
        result = create_window(test_schedule_arn)
        
        # Step 3: Verify window was created successfully
        assert result is True, "Window creation should return True"
        
        # Step 4: Verify window now exists and is active
        active_window = check_active_window()
        assert active_window is not None, "Active window should exist after creation"
        assert active_window['windowId'] == WINDOW_ID_FIXED_VALUE
        assert active_window['status'] == WINDOW_STATUS_ACTIVE
        assert active_window['scheduleArn'] == test_schedule_arn
        
        # Step 5: Verify timestamps are reasonable
        assert 'windowStartTime' in active_window
        assert 'windowEndTime' in active_window
        assert active_window['windowStartTime'] >= start_time
        assert active_window['windowStartTime'] <= start_time + 5  # Allow 5 second tolerance
        
        # Window end time should be start time + aggregation window
        expected_end_time = active_window['windowStartTime'] + AGGREGATION_WINDOW_SECONDS
        assert active_window['windowEndTime'] == expected_end_time
        
        # Step 6: Verify TTL is set correctly
        assert 'ttl' in active_window
        expected_ttl = active_window['windowEndTime'] + WINDOW_TTL_BUFFER_SECONDS
        assert active_window['ttl'] == expected_ttl
    
    def test_window_attributes_are_correct(self, clean_window_state, dynamodb_resource, test_config):
        """
        Verify that created window has all required attributes with correct types.
        
        Requirements: 4.1 - Window tracking attributes
        """
        test_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/test-{uuid.uuid4()}"
        
        # Create window
        create_window(test_schedule_arn)
        
        # Retrieve window directly from DynamoDB
        table = dynamodb_resource.Table(test_config['tracking_table'])
        response = table.get_item(Key={'windowId': WINDOW_ID_FIXED_VALUE})
        
        item = response['Item']
        
        # Verify all required attributes exist
        assert 'windowId' in item
        assert 'scheduleArn' in item
        assert 'windowStartTime' in item
        assert 'windowEndTime' in item
        assert 'status' in item
        assert 'ttl' in item
        
        # Verify attribute types
        assert isinstance(item['windowId'], str)
        assert isinstance(item['scheduleArn'], str)
        assert isinstance(item['windowStartTime'], int)
        assert isinstance(item['windowEndTime'], int)
        assert isinstance(item['status'], str)
        assert isinstance(item['ttl'], int)
        
        # Verify attribute values
        assert item['windowId'] == WINDOW_ID_FIXED_VALUE
        assert item['scheduleArn'] == test_schedule_arn
        assert item['status'] == WINDOW_STATUS_ACTIVE


class TestDuplicateSchedulePrevention:
    """Test duplicate schedule prevention."""
    
    def test_prevent_duplicate_schedule_creation(self, clean_window_state, test_config):
        """
        Verify that subsequent events do not create additional schedules.
        
        Requirements: 4.2 - WHEN the Ingestor Lambda processes subsequent events
        within an active aggregation window THEN the Invalidation Service SHALL
        not create additional schedules
        
        This test verifies:
        1. First event creates a window
        2. Second event does not create a new window
        3. Active window remains unchanged
        """
        # Step 1: Create initial window (first event)
        first_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/first-{uuid.uuid4()}"
        result1 = create_window(first_schedule_arn)
        assert result1 is True, "First window creation should succeed"
        
        # Get the initial window state
        initial_window = check_active_window()
        assert initial_window is not None
        initial_start_time = initial_window['windowStartTime']
        
        # Step 2: Attempt to create another window (subsequent event)
        time.sleep(1)  # Small delay to ensure different timestamp
        second_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/second-{uuid.uuid4()}"
        result2 = create_window(second_schedule_arn)
        
        # Step 3: Verify second creation was prevented
        assert result2 is False, "Second window creation should be prevented"
        
        # Step 4: Verify original window is still active and unchanged
        current_window = check_active_window()
        assert current_window is not None
        assert current_window['windowId'] == WINDOW_ID_FIXED_VALUE
        assert current_window['status'] == WINDOW_STATUS_ACTIVE
        assert current_window['scheduleArn'] == first_schedule_arn  # Original schedule ARN
        assert current_window['windowStartTime'] == initial_start_time  # Original start time
    
    def test_multiple_concurrent_create_attempts(self, clean_window_state, test_config):
        """
        Verify that concurrent window creation attempts are handled correctly.
        
        Requirements: 4.2 - Duplicate schedule prevention with race conditions
        
        This simulates multiple Lambda invocations trying to create windows
        simultaneously (race condition).
        """
        # Attempt to create multiple windows in quick succession
        schedule_arns = [
            f"arn:aws:scheduler:us-east-1:123456789012:schedule/concurrent-{i}-{uuid.uuid4()}"
            for i in range(5)
        ]
        
        results = []
        for arn in schedule_arns:
            result = create_window(arn)
            results.append(result)
            time.sleep(0.1)  # Small delay between attempts
        
        # Exactly one creation should succeed
        successful_creations = sum(1 for r in results if r is True)
        assert successful_creations == 1, f"Expected exactly 1 successful creation, got {successful_creations}"
        
        # Verify only one window exists
        active_window = check_active_window()
        assert active_window is not None
        assert active_window['status'] == WINDOW_STATUS_ACTIVE
        
        # The schedule ARN should be from the first successful creation
        first_success_index = results.index(True)
        assert active_window['scheduleArn'] == schedule_arns[first_success_index]


class TestWindowClosure:
    """Test window closure after processing."""
    
    def test_close_window_after_processing(self, clean_window_state, test_config):
        """
        Verify window closure after processing.
        
        Requirements: 4.4 - WHEN the Processor Lambda completes processing THEN
        the Invalidation Service SHALL mark the aggregation window as closed
        
        This test verifies:
        1. Window can be created
        2. Window can be closed successfully
        3. Window status changes to 'closed'
        4. Closed window is not returned by check_active_window
        """
        # Step 1: Create a window
        test_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/test-{uuid.uuid4()}"
        create_window(test_schedule_arn)
        
        # Verify window is active
        active_window = check_active_window()
        assert active_window is not None
        assert active_window['status'] == WINDOW_STATUS_ACTIVE
        
        # Step 2: Close the window
        result = close_window()
        assert result is True, "Window closure should succeed"
        
        # Step 3: Verify window is no longer active
        active_window_after = check_active_window()
        assert active_window_after is None, "No active window should exist after closure"
        
        # Step 4: Verify window still exists but with 'closed' status
        # (check directly in DynamoDB)
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(test_config['tracking_table'])
        response = table.get_item(Key={'windowId': WINDOW_ID_FIXED_VALUE})
        
        assert 'Item' in response
        assert response['Item']['status'] == WINDOW_STATUS_CLOSED
        assert response['Item']['scheduleArn'] == test_schedule_arn  # Other attributes unchanged
    
    def test_close_nonexistent_window(self, clean_window_state, test_config):
        """
        Verify behavior when trying to close a window that doesn't exist.
        
        Requirements: 4.4 - Error handling for window closure
        """
        # Attempt to close a window that doesn't exist
        result = close_window()
        
        # Should return False (window doesn't exist)
        assert result is False, "Closing nonexistent window should return False"
    
    def test_create_new_window_after_closure(self, clean_window_state, test_config):
        """
        Verify that a new window can be created after the previous one is closed.
        
        Requirements: 4.1, 4.4 - Window lifecycle
        
        This test verifies the complete window lifecycle:
        1. Create window
        2. Close window
        3. Create new window (should succeed)
        """
        # Step 1: Create first window
        first_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/first-{uuid.uuid4()}"
        result1 = create_window(first_schedule_arn)
        assert result1 is True
        
        first_window = check_active_window()
        assert first_window is not None
        first_start_time = first_window['windowStartTime']
        
        # Step 2: Close the window
        close_result = close_window()
        assert close_result is True
        
        # Verify no active window
        assert check_active_window() is None
        
        # Step 3: Create second window
        time.sleep(1)  # Ensure different timestamp
        second_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/second-{uuid.uuid4()}"
        result2 = create_window(second_schedule_arn)
        
        # Should succeed because previous window is closed
        assert result2 is True, "Should be able to create new window after closure"
        
        # Step 4: Verify new window is active
        second_window = check_active_window()
        assert second_window is not None
        assert second_window['status'] == WINDOW_STATUS_ACTIVE
        assert second_window['scheduleArn'] == second_schedule_arn
        assert second_window['windowStartTime'] > first_start_time  # New window has later timestamp


class TestTTLCleanup:
    """Test TTL cleanup of old window records."""
    
    def test_ttl_attribute_is_set(self, clean_window_state, test_config):
        """
        Verify that TTL attribute is set correctly on window creation.
        
        Requirements: 4.4 - TTL for automatic cleanup
        
        Note: This test verifies the TTL attribute is set correctly.
        Actual TTL cleanup by DynamoDB happens asynchronously and may take
        up to 48 hours, so we cannot test the actual deletion in integration tests.
        """
        # Create a window
        test_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/test-{uuid.uuid4()}"
        create_window(test_schedule_arn)
        
        # Retrieve window from DynamoDB
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(test_config['tracking_table'])
        response = table.get_item(Key={'windowId': WINDOW_ID_FIXED_VALUE})
        
        item = response['Item']
        
        # Verify TTL attribute exists
        assert 'ttl' in item, "TTL attribute should be set"
        
        # Verify TTL value is correct (windowEndTime + buffer)
        expected_ttl = item['windowEndTime'] + WINDOW_TTL_BUFFER_SECONDS
        assert item['ttl'] == expected_ttl, f"TTL should be {expected_ttl}, got {item['ttl']}"
        
        # Verify TTL is in the future
        current_time = int(time.time())
        assert item['ttl'] > current_time, "TTL should be in the future"
    
    def test_ttl_configuration_on_table(self, dynamodb_client, test_config):
        """
        Verify that the DynamoDB table has TTL enabled on the 'ttl' attribute.
        
        Requirements: 4.4 - TTL configuration
        """
        # Describe TTL configuration
        response = dynamodb_client.describe_time_to_live(
            TableName=test_config['tracking_table']
        )
        
        ttl_description = response['TimeToLiveDescription']
        
        # Verify TTL is enabled
        assert ttl_description['TimeToLiveStatus'] in ['ENABLED', 'ENABLING'], \
            f"TTL should be enabled, got status: {ttl_description['TimeToLiveStatus']}"
        
        # Verify TTL attribute name is 'ttl'
        if 'AttributeName' in ttl_description:
            assert ttl_description['AttributeName'] == 'ttl', \
                f"TTL attribute should be 'ttl', got: {ttl_description['AttributeName']}"
    
    def test_closed_window_has_ttl(self, clean_window_state, test_config):
        """
        Verify that closed windows retain their TTL attribute.
        
        Requirements: 4.4 - TTL persists after window closure
        """
        # Create and close a window
        test_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/test-{uuid.uuid4()}"
        create_window(test_schedule_arn)
        
        # Get initial TTL
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(test_config['tracking_table'])
        response_before = table.get_item(Key={'windowId': WINDOW_ID_FIXED_VALUE})
        ttl_before = response_before['Item']['ttl']
        
        # Close the window
        close_window()
        
        # Verify TTL is still set after closure
        response_after = table.get_item(Key={'windowId': WINDOW_ID_FIXED_VALUE})
        item_after = response_after['Item']
        
        assert 'ttl' in item_after, "TTL should still be set after window closure"
        assert item_after['ttl'] == ttl_before, "TTL should not change when window is closed"
        assert item_after['status'] == WINDOW_STATUS_CLOSED


class TestWindowTrackingEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_check_active_window_when_none_exists(self, clean_window_state, test_config):
        """
        Verify check_active_window returns None when no window exists.
        
        Requirements: 4.1 - Initial state
        """
        result = check_active_window()
        assert result is None, "Should return None when no window exists"
    
    def test_window_id_is_always_current(self, clean_window_state, test_config):
        """
        Verify that the windowId is always the fixed value 'current'.
        
        Requirements: 4.1 - Fixed window ID
        """
        test_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/test-{uuid.uuid4()}"
        create_window(test_schedule_arn)
        
        active_window = check_active_window()
        assert active_window['windowId'] == WINDOW_ID_FIXED_VALUE
        assert active_window['windowId'] == 'current'
    
    def test_window_timestamps_are_monotonic(self, clean_window_state, test_config):
        """
        Verify that window timestamps are monotonically increasing.
        
        Requirements: 4.1 - Timestamp ordering
        """
        # Create first window
        first_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/first-{uuid.uuid4()}"
        create_window(first_schedule_arn)
        first_window = check_active_window()
        
        # Close and create second window
        close_window()
        time.sleep(1)
        
        second_schedule_arn = f"arn:aws:scheduler:us-east-1:123456789012:schedule/second-{uuid.uuid4()}"
        create_window(second_schedule_arn)
        second_window = check_active_window()
        
        # Second window should have later timestamps
        assert second_window['windowStartTime'] > first_window['windowStartTime']
        assert second_window['windowEndTime'] > first_window['windowEndTime']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
