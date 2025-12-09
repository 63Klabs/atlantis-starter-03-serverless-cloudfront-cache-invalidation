"""Property-based tests for Processor SQS message operations."""

import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from hypothesis import given, settings, strategies as st
from processor.queue_client import (
    receive_messages_batch,
    delete_message,
    delete_messages_batch
)


# Custom strategies for generating test data

@st.composite
def sqs_message(draw):
    """Generate a mock SQS message structure."""
    message_id = draw(st.text(min_size=10, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Nd'), whitelist_characters='-'
    )))
    
    receipt_handle = draw(st.text(min_size=50, max_size=200, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='+/='
    )))
    
    # Generate message body with S3 event metadata
    stage_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_'
    )))
    
    bucket_name = draw(st.text(min_size=1, max_size=63, alphabet=st.characters(
        whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'
    )).filter(lambda x: x and not x.startswith('-') and not x.endswith('-')))
    
    object_key = f"/{stage_id}/public/test-file.txt"
    origin_path = f"/{stage_id}/public"
    
    event_time = draw(st.datetimes().map(lambda dt: dt.isoformat() + 'Z'))
    event_type = draw(st.sampled_from([
        'ObjectCreated:Put',
        'ObjectCreated:Post',
        'ObjectCreated:Copy',
        'ObjectRemoved:Delete'
    ]))
    
    body = {
        'bucketName': bucket_name,
        'objectKey': object_key,
        'originPath': origin_path,
        'stageId': stage_id,
        'eventTime': event_time,
        'eventType': event_type
    }
    
    return {
        'MessageId': message_id,
        'ReceiptHandle': receipt_handle,
        'Body': json.dumps(body)
    }


@st.composite
def sqs_message_list(draw):
    """Generate a list of SQS messages."""
    messages = draw(st.lists(sqs_message(), min_size=1, max_size=10))
    return messages


# Property Tests

@settings(max_examples=100)
@given(sqs_message())
def test_property_13_message_deletion_after_successful_processing(message):
    """Property 13: Message deletion after successful processing.
    
    For any SQS message that is successfully processed, the message should be
    deleted from the queue using its receipt handle.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 13: Message deletion after successful processing**
    **Validates: Requirements 5.3**
    """
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    receipt_handle = message['ReceiptHandle']
    
    # Mock the SQS client
    with patch('processor.queue_client.get_sqs_client') as mock_get_client:
        mock_sqs = Mock()
        mock_get_client.return_value = mock_sqs
        
        # Mock successful deletion
        mock_sqs.delete_message.return_value = {}
        
        # Call delete_message
        delete_message(queue_url, receipt_handle)
        
        # Verify delete_message was called with correct parameters
        mock_sqs.delete_message.assert_called_once()
        call_args = mock_sqs.delete_message.call_args
        
        # Verify the queue URL and receipt handle were passed correctly
        assert call_args[1]['QueueUrl'] == queue_url, \
            "delete_message should be called with the correct queue URL"
        assert call_args[1]['ReceiptHandle'] == receipt_handle, \
            "delete_message should be called with the correct receipt handle"


@settings(max_examples=100)
@given(sqs_message_list())
def test_property_13_batch_deletion_after_successful_processing(messages):
    """Property 13: Batch message deletion after successful processing.
    
    For any list of SQS messages that are successfully processed, all messages
    should be deleted from the queue in batch operations.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 13: Message deletion after successful processing**
    **Validates: Requirements 5.3**
    """
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    receipt_handles = [msg['ReceiptHandle'] for msg in messages]
    
    # Mock the SQS client
    with patch('processor.queue_client.get_sqs_client') as mock_get_client:
        mock_sqs = Mock()
        mock_get_client.return_value = mock_sqs
        
        # Mock successful batch deletion
        # SQS returns successful deletions in the response
        successful_responses = [
            {'Id': str(i)} for i in range(len(messages))
        ]
        mock_sqs.delete_message_batch.return_value = {
            'Successful': successful_responses,
            'Failed': []
        }
        
        # Call delete_messages_batch
        result = delete_messages_batch(queue_url, receipt_handles)
        
        # Verify all messages were marked as successfully deleted
        assert len(result['successful']) == len(receipt_handles), \
            "All messages should be successfully deleted"
        assert len(result['failed']) == 0, \
            "No messages should fail deletion"
        
        # Verify delete_message_batch was called
        assert mock_sqs.delete_message_batch.called, \
            "delete_message_batch should be called"
        
        # Verify the queue URL was correct
        for call in mock_sqs.delete_message_batch.call_args_list:
            assert call[1]['QueueUrl'] == queue_url, \
                "delete_message_batch should be called with the correct queue URL"


@settings(max_examples=100)
@given(sqs_message_list())
def test_property_receive_messages_returns_parseable_bodies(messages):
    """Property: Received messages have parseable JSON bodies.
    
    For any list of messages received from SQS, each message body should be
    valid JSON that can be parsed into the expected structure.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 13: Message deletion after successful processing**
    **Validates: Requirements 5.1**
    """
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    
    # Mock the SQS client
    with patch('processor.queue_client.get_sqs_client') as mock_get_client:
        mock_sqs = Mock()
        mock_get_client.return_value = mock_sqs
        
        # Mock receive_message to return our test messages
        mock_sqs.receive_message.return_value = {
            'Messages': messages
        }
        
        # Call receive_messages_batch
        received = receive_messages_batch(queue_url, max_messages=len(messages))
        
        # Verify all messages were received and parsed
        assert len(received) == len(messages), \
            "All messages should be received"
        
        # Verify each message has a parsed_body
        for msg in received:
            assert 'parsed_body' in msg, \
                "Each message should have a parsed_body field"
            assert isinstance(msg['parsed_body'], dict), \
                "parsed_body should be a dictionary"
            
            # Verify required fields are present in parsed body
            parsed = msg['parsed_body']
            assert 'bucketName' in parsed, "parsed_body should contain bucketName"
            assert 'objectKey' in parsed, "parsed_body should contain objectKey"
            assert 'originPath' in parsed, "parsed_body should contain originPath"
            assert 'stageId' in parsed, "parsed_body should contain stageId"
            assert 'eventTime' in parsed, "parsed_body should contain eventTime"
            assert 'eventType' in parsed, "parsed_body should contain eventType"


@settings(max_examples=100)
@given(st.integers(min_value=1, max_value=10))
def test_property_receive_messages_handles_empty_queue(max_messages):
    """Property: Empty queue returns empty list gracefully.
    
    For any valid max_messages parameter, when the queue is empty,
    receive_messages_batch should return an empty list without errors.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 13: Message deletion after successful processing**
    **Validates: Requirements 5.1**
    """
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    
    # Mock the SQS client
    with patch('processor.queue_client.get_sqs_client') as mock_get_client:
        mock_sqs = Mock()
        mock_get_client.return_value = mock_sqs
        
        # Mock empty queue response
        mock_sqs.receive_message.return_value = {}
        
        # Call receive_messages_batch
        received = receive_messages_batch(queue_url, max_messages=max_messages)
        
        # Verify empty list is returned
        assert received == [], \
            "Empty queue should return an empty list"
        
        # Verify receive_message was called with correct parameters
        mock_sqs.receive_message.assert_called_once()
        call_args = mock_sqs.receive_message.call_args
        
        assert call_args[1]['QueueUrl'] == queue_url, \
            "receive_message should be called with correct queue URL"
        assert call_args[1]['MaxNumberOfMessages'] == max_messages, \
            "receive_message should be called with correct max_messages"
