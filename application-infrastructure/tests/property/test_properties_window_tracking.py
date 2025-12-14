"""Property-based tests for DynamoDB window tracking."""

import os
import time
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from hypothesis import given, settings, strategies as st
from botocore.exceptions import ClientError

from functions.ingestor.window_tracker import check_active_window, create_window, close_window
from common.constants import (
    WINDOW_ID_FIXED_VALUE,
    WINDOW_STATUS_ACTIVE,
    WINDOW_STATUS_CLOSED,
    AGGREGATION_WINDOW_SECONDS,
    WINDOW_TTL_BUFFER_SECONDS
)


# Custom strategies for generating test data

@st.composite
def schedule_arn(draw):
    """Generate a valid EventBridge Scheduler ARN."""
    account_id = draw(st.integers(min_value=100000000000, max_value=999999999999))
    region = draw(st.sampled_from(['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1']))
    schedule_name = draw(st.text(
        min_size=1,
        max_size=64,
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_.')
    ))
    return f"arn:aws:scheduler:{region}:{account_id}:schedule/default/{schedule_name}"


# Property Tests

@settings(max_examples=100)
@given(schedule_arn())
def test_property_9_schedule_creation_for_first_event(arn):
    """Property 9: Schedule creation for first event.
    
    For any event processed when no active aggregation window exists,
    a new EventBridge schedule should be created with a target time 5 minutes in the future.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 9: Schedule creation for first event**
    **Validates: Requirements 4.1**
    """
    # Mock DynamoDB table
    mock_table = MagicMock()
    
    # Simulate no active window exists (GetItem returns empty)
    mock_table.get_item.return_value = {}
    
    # Simulate successful PutItem (window creation)
    mock_table.put_item.return_value = {}
    
    with patch.dict(os.environ, {'TRACKING_TABLE': 'test-table'}):
        with patch('ingestor.window_tracker.get_tracking_table', return_value=mock_table):
            # Check that no active window exists
            active_window = check_active_window()
            assert active_window is None, "No active window should exist initially"
            
            # Record time before creating window
            time_before = int(time.time())
            
            # Create a new window
            result = create_window(arn)
            
            # Record time after creating window
            time_after = int(time.time())
            
            # Verify window was created successfully
            assert result is True, "Window creation should succeed when no active window exists"
            
            # Verify PutItem was called
            assert mock_table.put_item.called, "PutItem should be called to create window"
            
            # Extract the item that was written
            call_args = mock_table.put_item.call_args
            item = call_args[1]['Item']
            
            # Verify window structure
            assert item['windowId'] == WINDOW_ID_FIXED_VALUE
            assert item['scheduleArn'] == arn
            assert item['status'] == WINDOW_STATUS_ACTIVE
            
            # Verify timing: windowStartTime should be approximately current time
            assert time_before <= item['windowStartTime'] <= time_after + 1
            
            # Verify windowEndTime is approximately 5 minutes (300 seconds) in the future
            expected_end_time = item['windowStartTime'] + AGGREGATION_WINDOW_SECONDS
            assert item['windowEndTime'] == expected_end_time
            
            # Verify TTL is set correctly (1 hour after window end)
            expected_ttl = expected_end_time + WINDOW_TTL_BUFFER_SECONDS
            assert item['ttl'] == expected_ttl
            
            # Verify conditional expression prevents duplicates
            assert 'ConditionExpression' in call_args[1]


@settings(max_examples=100)
@given(schedule_arn(), schedule_arn())
def test_property_10_schedule_prevention_for_subsequent_events(first_arn, second_arn):
    """Property 10: Schedule prevention for subsequent events.
    
    For any event processed when an active aggregation window exists,
    no new EventBridge schedule should be created.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 10: Schedule prevention for subsequent events**
    **Validates: Requirements 4.2**
    """
    # Mock DynamoDB table
    mock_table = MagicMock()
    
    current_time = int(time.time())
    
    # Simulate active window exists
    active_window_item = {
        'windowId': WINDOW_ID_FIXED_VALUE,
        'scheduleArn': first_arn,
        'windowStartTime': current_time,
        'windowEndTime': current_time + AGGREGATION_WINDOW_SECONDS,
        'status': WINDOW_STATUS_ACTIVE,
        'ttl': current_time + AGGREGATION_WINDOW_SECONDS + WINDOW_TTL_BUFFER_SECONDS
    }
    
    mock_table.get_item.return_value = {'Item': active_window_item}
    
    # Simulate ConditionalCheckFailedException when trying to create duplicate window
    conditional_error = ClientError(
        {
            'Error': {
                'Code': 'ConditionalCheckFailedException',
                'Message': 'The conditional request failed'
            }
        },
        'PutItem'
    )
    mock_table.put_item.side_effect = conditional_error
    
    with patch.dict(os.environ, {'TRACKING_TABLE': 'test-table'}):
        with patch('ingestor.window_tracker.get_tracking_table', return_value=mock_table):
            # Check that active window exists
            active_window = check_active_window()
            assert active_window is not None, "Active window should exist"
            assert active_window['scheduleArn'] == first_arn
            
            # Attempt to create a new window (should fail due to active window)
            result = create_window(second_arn)
            
            # Verify window creation was prevented
            assert result is False, "Window creation should fail when active window exists"
            
            # Verify PutItem was attempted but failed due to condition
            assert mock_table.put_item.called, "PutItem should be attempted"


@settings(max_examples=100)
@given(schedule_arn())
def test_property_11_window_closure_after_processing(arn):
    """Property 11: Window closure after processing.
    
    For any completed Processor Lambda execution, the aggregation window status
    in DynamoDB should be updated to "closed".
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 11: Window closure after processing**
    **Validates: Requirements 4.4**
    """
    # Mock DynamoDB table
    mock_table = MagicMock()
    
    current_time = int(time.time())
    
    # Simulate successful window closure
    updated_item = {
        'windowId': WINDOW_ID_FIXED_VALUE,
        'scheduleArn': arn,
        'windowStartTime': current_time - AGGREGATION_WINDOW_SECONDS,
        'windowEndTime': current_time,
        'status': WINDOW_STATUS_CLOSED,
        'ttl': current_time + WINDOW_TTL_BUFFER_SECONDS
    }
    
    mock_table.update_item.return_value = {'Attributes': updated_item}
    
    with patch.dict(os.environ, {'TRACKING_TABLE': 'test-table'}):
        with patch('ingestor.window_tracker.get_tracking_table', return_value=mock_table):
            # Close the window
            result = close_window()
            
            # Verify window was closed successfully
            assert result is True, "Window closure should succeed"
            
            # Verify UpdateItem was called
            assert mock_table.update_item.called, "UpdateItem should be called to close window"
            
            # Extract the update parameters
            call_args = mock_table.update_item.call_args
            
            # Verify the correct key was used
            assert call_args[1]['Key'] == {'windowId': WINDOW_ID_FIXED_VALUE}
            
            # Verify status was updated to closed
            assert call_args[1]['UpdateExpression'] == 'SET #status = :closed'
            assert call_args[1]['ExpressionAttributeValues'][':closed'] == WINDOW_STATUS_CLOSED
            
            # Verify conditional expression ensures window exists
            assert 'ConditionExpression' in call_args[1]
            assert 'attribute_exists(windowId)' in call_args[1]['ConditionExpression']
