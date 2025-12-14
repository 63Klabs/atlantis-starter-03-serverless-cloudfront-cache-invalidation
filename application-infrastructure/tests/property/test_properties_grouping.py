"""Property-based tests for message grouping in Processor."""

import sys
import os

from hypothesis import given, settings, strategies as st
from functions.processor.handler import group_messages_by_bucket_and_origin


# Custom strategies for generating test data

@st.composite
def sqs_message(draw):
    """Generate a single SQS message with parsed S3 event data."""
    # Generate bucket name
    bucket_name = draw(st.text(min_size=1, max_size=63, alphabet=st.characters(
        whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'
    )).filter(lambda x: x and not x.startswith('-') and not x.endswith('-')))
    
    # Generate stage_id
    stage_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_'
    )))
    
    # Origin path is /<StageId>/public
    origin_path = f"/{stage_id}/public"
    
    # Generate object key with path segments
    path_parts = draw(st.lists(
        st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
        )),
        min_size=1,
        max_size=5
    ))
    object_key = f"{origin_path}/" + "/".join(path_parts)
    
    # Generate event time (ISO 8601 format)
    event_time = draw(st.datetimes().map(lambda dt: dt.isoformat() + 'Z'))
    
    # Generate event type
    event_type = draw(st.sampled_from([
        'ObjectCreated:Put',
        'ObjectCreated:Post',
        'ObjectCreated:Copy',
        'ObjectRemoved:Delete'
    ]))
    
    # Generate message ID
    message_id = draw(st.text(min_size=10, max_size=100, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-'
    )))
    
    # Generate receipt handle
    receipt_handle = draw(st.text(min_size=20, max_size=200, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_='
    )))
    
    return {
        'MessageId': message_id,
        'ReceiptHandle': receipt_handle,
        'Body': '{}',  # Not used since we have parsed_body
        'parsed_body': {
            'bucketName': bucket_name,
            'objectKey': object_key,
            'originPath': origin_path,
            'stageId': stage_id,
            'eventTime': event_time,
            'eventType': event_type
        }
    }


@st.composite
def sqs_message_list(draw):
    """Generate a list of SQS messages."""
    messages = draw(st.lists(sqs_message(), min_size=0, max_size=50))
    return messages


# Property Tests

@settings(max_examples=100)
@given(sqs_message_list())
def test_property_12_event_grouping_by_bucket_and_origin(messages):
    """Property 12: Event grouping by bucket and origin.
    
    For any set of SQS messages, grouping them by bucketName and originPath
    should result in groups where all messages in each group share the same
    bucketName and originPath.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 12: Event grouping by bucket and origin**
    **Validates: Requirements 5.2**
    """
    # Group the messages
    grouped = group_messages_by_bucket_and_origin(messages)
    
    # Property 1: All messages in a group must have the same bucketName and originPath
    for (bucket_name, origin_path), group_messages in grouped.items():
        for message in group_messages:
            parsed_body = message.get('parsed_body', {})
            
            # Verify bucket name matches the group key
            assert parsed_body.get('bucketName') == bucket_name, \
                f"Message in group has bucketName '{parsed_body.get('bucketName')}' but group key is '{bucket_name}'"
            
            # Verify origin path matches the group key
            assert parsed_body.get('originPath') == origin_path, \
                f"Message in group has originPath '{parsed_body.get('originPath')}' but group key is '{origin_path}'"
    
    # Property 2: No message should be lost during grouping
    # (except messages with missing bucketName or originPath)
    valid_messages = [
        msg for msg in messages
        if msg.get('parsed_body', {}).get('bucketName') and
           msg.get('parsed_body', {}).get('originPath')
    ]
    
    # Count messages in all groups
    grouped_message_count = sum(len(group) for group in grouped.values())
    
    assert grouped_message_count == len(valid_messages), \
        f"Expected {len(valid_messages)} messages in groups, but found {grouped_message_count}"
    
    # Property 3: Each unique (bucket, origin) combination should have exactly one group
    unique_combinations = set()
    for message in valid_messages:
        parsed_body = message.get('parsed_body', {})
        bucket = parsed_body.get('bucketName')
        origin = parsed_body.get('originPath')
        unique_combinations.add((bucket, origin))
    
    assert len(grouped) == len(unique_combinations), \
        f"Expected {len(unique_combinations)} groups, but found {len(grouped)}"
    
    # Property 4: All group keys should correspond to valid messages
    for (bucket_name, origin_path) in grouped.keys():
        # Verify at least one message has this combination
        found = False
        for message in valid_messages:
            parsed_body = message.get('parsed_body', {})
            if (parsed_body.get('bucketName') == bucket_name and
                parsed_body.get('originPath') == origin_path):
                found = True
                break
        
        assert found, \
            f"Group key ({bucket_name}, {origin_path}) does not correspond to any message"


@settings(max_examples=100)
@given(st.lists(sqs_message(), min_size=1, max_size=20, unique_by=lambda m: m['MessageId']))
def test_property_12_grouping_preserves_message_identity(messages):
    """Property 12 (variant): Grouping preserves message identity.
    
    For any set of messages, each message in the grouped output should be
    identical to a message in the input (same MessageId and ReceiptHandle).
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 12: Event grouping by bucket and origin**
    **Validates: Requirements 5.2**
    """
    # Group the messages
    grouped = group_messages_by_bucket_and_origin(messages)
    
    # Collect all messages from groups
    all_grouped_messages = []
    for group_messages in grouped.values():
        all_grouped_messages.extend(group_messages)
    
    # Create sets of message IDs for comparison
    input_message_ids = {msg['MessageId'] for msg in messages
                         if msg.get('parsed_body', {}).get('bucketName') and
                            msg.get('parsed_body', {}).get('originPath')}
    
    output_message_ids = {msg['MessageId'] for msg in all_grouped_messages}
    
    # Verify all grouped messages came from the input
    assert output_message_ids.issubset(input_message_ids), \
        "Grouped messages contain MessageIds not in input"
    
    # Verify no messages were duplicated
    assert len(all_grouped_messages) == len(output_message_ids), \
        "Some messages were duplicated during grouping"
    
    # Verify message content is preserved
    for grouped_msg in all_grouped_messages:
        # Find the original message
        original = next(
            (msg for msg in messages if msg['MessageId'] == grouped_msg['MessageId']),
            None
        )
        
        assert original is not None, \
            f"Grouped message with ID {grouped_msg['MessageId']} not found in input"
        
        # Verify the message is identical (same object reference or equal content)
        assert grouped_msg['MessageId'] == original['MessageId']
        assert grouped_msg['ReceiptHandle'] == original['ReceiptHandle']
        assert grouped_msg['parsed_body'] == original['parsed_body']
