"""Property-based tests for Ingestor Lambda handler."""

import sys
import os
import json
import io
from unittest.mock import Mock, patch, MagicMock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from hypothesis import given, settings, strategies as st
from ingestor.handler import process_s3_record


# Custom strategies for generating test data

@st.composite
def valid_s3_event_record(draw):
    """Generate a valid S3 event record structure."""
    bucket_name = draw(st.text(min_size=1, max_size=63, alphabet=st.characters(
        whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'
    )).filter(lambda x: x and not x.startswith('-') and not x.endswith('-')))
    
    # Generate production StageId (p*, s*, b*)
    stage_prefix = draw(st.sampled_from(['p', 's', 'b', 'P', 'S', 'B']))
    stage_suffix = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_'
    )))
    stage_id = stage_prefix + stage_suffix
    
    # Generate public path with at least one file/folder after /public
    path_parts = draw(st.lists(
        st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
        )),
        min_size=1,
        max_size=5
    ))
    object_key = f"/{stage_id}/public/" + "/".join(path_parts)
    
    event_time = draw(st.datetimes().map(lambda dt: dt.isoformat() + 'Z'))
    event_type = draw(st.sampled_from([
        'ObjectCreated:Put',
        'ObjectCreated:Post',
        'ObjectCreated:Copy',
        'ObjectRemoved:Delete'
    ]))
    
    return {
        's3': {
            'bucket': {'name': bucket_name},
            'object': {'key': object_key}
        },
        'eventTime': event_time,
        'eventName': event_type
    }


# Property Tests

@settings(max_examples=100)
@given(valid_s3_event_record())
def test_property_3_event_logging_contains_required_fields(record):
    """Property 3: Event logging contains required fields.
    
    For any processed S3 event, the JSON log output should contain the fields
    bucketName, originPath, stageId, and objectKey.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 3: Event logging contains required fields**
    **Validates: Requirements 1.3**
    """
    # Mock the queue URL
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    
    # Mock all external dependencies
    with patch('ingestor.handler.send_event_to_queue') as mock_send, \
         patch('ingestor.handler.check_active_window') as mock_check_window, \
         patch('ingestor.handler.create_one_time_schedule') as mock_create_schedule, \
         patch('ingestor.handler.create_window') as mock_create_window, \
         patch('ingestor.handler.logger') as mock_logger:
        
        # Configure mocks
        mock_send.return_value = 'mock-message-id-123'
        mock_check_window.return_value = None  # No active window
        mock_create_schedule.return_value = 'arn:aws:scheduler:us-east-1:123456789012:schedule/test'
        mock_create_window.return_value = True
        
        # Process the record
        result = process_s3_record(record, queue_url)
        
        # Verify processing succeeded
        assert result['success'] is True
        
        # Extract the expected values from the record
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        
        # Extract stage_id and origin_path from object_key
        path_parts = object_key.lstrip('/').split('/')
        stage_id = path_parts[0] if len(path_parts) > 0 else None
        origin_path = f"/{stage_id}/public" if len(path_parts) >= 2 and path_parts[1] == 'public' else None
        
        # Find the log call for "Processing S3 event"
        processing_log_call = None
        for call in mock_logger.info.call_args_list:
            if len(call[0]) > 0 and 'Processing S3 event' in call[0][0]:
                processing_log_call = call
                break
        
        # Verify the processing log call exists
        assert processing_log_call is not None, "Processing log call not found"
        
        # Extract the extra fields from the log call
        extra_fields = processing_log_call[1].get('extra', {}).get('extra_fields', {})
        
        # Verify all required fields are present in the log
        assert 'bucketName' in extra_fields, "bucketName not in log"
        assert 'originPath' in extra_fields, "originPath not in log"
        assert 'stageId' in extra_fields, "stageId not in log"
        assert 'objectKey' in extra_fields, "objectKey not in log"
        
        # Verify the values match
        assert extra_fields['bucketName'] == bucket_name
        assert extra_fields['objectKey'] == object_key
        assert extra_fields['stageId'] == stage_id
        assert extra_fields['originPath'] == origin_path
