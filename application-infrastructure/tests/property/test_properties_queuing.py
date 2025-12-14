"""Property-based tests for SQS message queuing."""

import sys
import os

from hypothesis import given, settings, strategies as st
from functions.ingestor.queue_client import format_sqs_message


# Custom strategies for generating test data

@st.composite
def s3_event_metadata(draw):
    """Generate S3 event metadata for SQS message formatting."""
    bucket_name = draw(st.text(min_size=1, max_size=63, alphabet=st.characters(
        whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'
    )).filter(lambda x: x and not x.startswith('-') and not x.endswith('-')))
    
    # Generate stage_id
    stage_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_'
    )))
    
    # Generate object key with path segments
    path_parts = draw(st.lists(
        st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
        )),
        min_size=1,
        max_size=5
    ))
    object_key = f"/{stage_id}/public/" + "/".join(path_parts)
    
    # Origin path is /<StageId>/public
    origin_path = f"/{stage_id}/public"
    
    # Generate event time (ISO 8601 format)
    event_time = draw(st.datetimes().map(lambda dt: dt.isoformat() + 'Z'))
    
    # Generate event type
    event_type = draw(st.sampled_from([
        'ObjectCreated:Put',
        'ObjectCreated:Post',
        'ObjectCreated:Copy',
        'ObjectRemoved:Delete'
    ]))
    
    return {
        'bucket_name': bucket_name,
        'object_key': object_key,
        'origin_path': origin_path,
        'stage_id': stage_id,
        'event_time': event_time,
        'event_type': event_type
    }


# Property Tests

@settings(max_examples=100)
@given(s3_event_metadata())
def test_property_8_sqs_message_format_completeness(metadata):
    """Property 8: SQS message format completeness.
    
    For any validated S3 event, the SQS message should contain all required fields:
    bucketName, objectKey, originPath, stageId, and eventTime.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 8: SQS message format completeness**
    **Validates: Requirements 3.1**
    """
    # Format the SQS message
    message = format_sqs_message(
        bucket_name=metadata['bucket_name'],
        object_key=metadata['object_key'],
        origin_path=metadata['origin_path'],
        stage_id=metadata['stage_id'],
        event_time=metadata['event_time'],
        event_type=metadata['event_type']
    )
    
    # Verify all required fields are present
    assert 'bucketName' in message, "Message missing 'bucketName' field"
    assert 'objectKey' in message, "Message missing 'objectKey' field"
    assert 'originPath' in message, "Message missing 'originPath' field"
    assert 'stageId' in message, "Message missing 'stageId' field"
    assert 'eventTime' in message, "Message missing 'eventTime' field"
    assert 'eventType' in message, "Message missing 'eventType' field"
    
    # Verify fields are non-empty
    assert message['bucketName'], "bucketName field is empty"
    assert message['objectKey'], "objectKey field is empty"
    assert message['originPath'], "originPath field is empty"
    assert message['stageId'], "stageId field is empty"
    assert message['eventTime'], "eventTime field is empty"
    assert message['eventType'], "eventType field is empty"
    
    # Verify fields match the input
    assert message['bucketName'] == metadata['bucket_name']
    assert message['objectKey'] == metadata['object_key']
    assert message['originPath'] == metadata['origin_path']
    assert message['stageId'] == metadata['stage_id']
    assert message['eventTime'] == metadata['event_time']
    assert message['eventType'] == metadata['event_type']
