"""Property-based tests for S3 event parsing and filtering."""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from hypothesis import given, settings, strategies as st
from ingestor.event_parser import extract_event_metadata, extract_stage_id, S3EventParseError
from ingestor.event_filter import is_production_stage, matches_public_path_pattern


# Custom strategies for generating test data

@st.composite
def valid_s3_event_record(draw):
    """Generate a valid S3 event record structure."""
    bucket_name = draw(st.text(min_size=1, max_size=63, alphabet=st.characters(
        whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'
    )).filter(lambda x: x and not x.startswith('-') and not x.endswith('-')))
    
    # Generate object key with at least one path segment
    stage_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd')
    )))
    path_parts = draw(st.lists(
        st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
        )),
        min_size=1,
        max_size=5
    ))
    object_key = f"/{stage_id}/" + "/".join(path_parts)
    
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


@st.composite
def object_key_with_segments(draw, min_segments=1, max_segments=10):
    """Generate an object key with a specified number of segments."""
    segments = draw(st.lists(
        st.text(min_size=1, max_size=30, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
        )),
        min_size=min_segments,
        max_size=max_segments
    ))
    return '/' + '/'.join(segments)


@st.composite
def stage_id_text(draw, production=None):
    """Generate a StageId string.
    
    Args:
        production: If True, generate production StageId (p*, s*, b*).
                   If False, generate non-production StageId.
                   If None, generate any StageId.
    """
    if production is True:
        prefix = draw(st.sampled_from(['p', 's', 'b', 'P', 'S', 'B']))
        suffix = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_'
        )))
        return prefix + suffix
    elif production is False:
        # Generate non-production StageId (not starting with p, s, b)
        prefix = draw(st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd')
        ).filter(lambda c: c.lower() not in ['p', 's', 'b']))
        suffix = draw(st.text(min_size=0, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_'
        )))
        return prefix + suffix
    else:
        return draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_'
        )))


@st.composite
def public_path_object_key(draw):
    """Generate an object key matching the public path pattern (/<StageId>/public/*)."""
    stage_id = draw(stage_id_text())
    # Add at least one path segment after /public
    path_parts = draw(st.lists(
        st.text(min_size=1, max_size=30, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
        )),
        min_size=1,
        max_size=5
    ))
    return f"/{stage_id}/public/" + "/".join(path_parts)


@st.composite
def non_public_path_object_key(draw):
    """Generate an object key NOT matching the public path pattern."""
    choice = draw(st.integers(min_value=0, max_value=2))
    
    if choice == 0:
        # Too few segments (less than 3)
        segments = draw(st.lists(
            st.text(min_size=1, max_size=30, alphabet=st.characters(
                whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
            )),
            min_size=0,
            max_size=2
        ))
        if segments:
            return '/' + '/'.join(segments)
        else:
            return '/'
    elif choice == 1:
        # Second segment is not 'public'
        stage_id = draw(stage_id_text())
        not_public = draw(st.text(min_size=1, max_size=30, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
        )).filter(lambda x: x != 'public'))
        path_parts = draw(st.lists(
            st.text(min_size=1, max_size=30, alphabet=st.characters(
                whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
            )),
            min_size=1,
            max_size=5
        ))
        return f"/{stage_id}/{not_public}/" + "/".join(path_parts)
    else:
        # Has 'public' but not in the right position
        stage_id = draw(stage_id_text())
        path_parts = draw(st.lists(
            st.text(min_size=1, max_size=30, alphabet=st.characters(
                whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='.-_'
            )),
            min_size=2,
            max_size=5
        ))
        # Insert 'public' somewhere other than position 1
        insert_pos = draw(st.integers(min_value=2, max_value=len(path_parts)))
        path_parts.insert(insert_pos, 'public')
        return f"/{stage_id}/" + "/".join(path_parts)


# Property Tests

@settings(max_examples=100)
@given(valid_s3_event_record())
def test_property_1_s3_event_field_extraction_completeness(record):
    """Property 1: S3 event field extraction completeness.
    
    For any valid S3 event notification, parsing the event should successfully
    extract bucketName, objectKey, eventTime, and eventType without errors.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 1: S3 event field extraction completeness**
    **Validates: Requirements 1.1**
    """
    # Extract metadata - should not raise an exception
    metadata = extract_event_metadata(record)
    
    # Verify all required fields are present
    assert 'bucketName' in metadata
    assert 'objectKey' in metadata
    assert 'eventTime' in metadata
    assert 'eventType' in metadata
    
    # Verify fields are non-empty
    assert metadata['bucketName']
    assert metadata['objectKey']
    assert metadata['eventTime']
    assert metadata['eventType']
    
    # Verify fields match the input
    assert metadata['bucketName'] == record['s3']['bucket']['name']
    assert metadata['objectKey'] == record['s3']['object']['key']
    assert metadata['eventTime'] == record['eventTime']
    assert metadata['eventType'] == record['eventName']


@settings(max_examples=100)
@given(object_key_with_segments(min_segments=1, max_segments=10))
def test_property_2_stage_id_extraction_from_object_key(object_key):
    """Property 2: StageId extraction from object key.
    
    For any object key with at least one path segment, extracting the StageId
    should return the first non-empty segment after the leading slash.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 2: StageId extraction from object key**
    **Validates: Requirements 1.2**
    """
    stage_id = extract_stage_id(object_key)
    
    # Extract expected stage_id manually
    path_segments = object_key.lstrip('/').split('/')
    non_empty_segments = [seg for seg in path_segments if seg]
    
    if non_empty_segments:
        expected_stage_id = non_empty_segments[0]
        assert stage_id == expected_stage_id
    else:
        assert stage_id is None


@settings(max_examples=100)
@given(stage_id_text(production=True))
def test_property_4_production_stage_id_filter_acceptance(stage_id):
    """Property 4: Production StageId filter acceptance.
    
    For any StageId starting with 'p', 's', or 'b' (case-insensitive),
    the filter should accept the event for processing.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 4: Production StageId filter acceptance**
    **Validates: Requirements 2.1**
    """
    result = is_production_stage(stage_id)
    assert result is True, f"StageId '{stage_id}' should be accepted as production"


@settings(max_examples=100)
@given(stage_id_text(production=False))
def test_property_5_non_production_stage_id_filter_rejection(stage_id):
    """Property 5: Non-production StageId filter rejection.
    
    For any StageId not starting with 'p', 's', or 'b', the filter should
    reject the event and log the rejection reason.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 5: Non-production StageId filter rejection**
    **Validates: Requirements 2.2**
    """
    result = is_production_stage(stage_id)
    assert result is False, f"StageId '{stage_id}' should be rejected as non-production"


@settings(max_examples=100)
@given(public_path_object_key())
def test_property_6_public_path_pattern_acceptance(object_key):
    """Property 6: Public path pattern acceptance.
    
    For any object key matching the pattern /<StageId>/public/*,
    the path filter should accept the event for processing.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 6: Public path pattern acceptance**
    **Validates: Requirements 2.3**
    """
    result = matches_public_path_pattern(object_key)
    assert result is True, f"Object key '{object_key}' should match public path pattern"


@settings(max_examples=100)
@given(non_public_path_object_key())
def test_property_7_non_public_path_pattern_rejection(object_key):
    """Property 7: Non-public path pattern rejection.
    
    For any object key not matching the pattern /<StageId>/public/*,
    the path filter should reject the event and log the rejection reason.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 7: Non-public path pattern rejection**
    **Validates: Requirements 2.4**
    """
    result = matches_public_path_pattern(object_key)
    assert result is False, f"Object key '{object_key}' should not match public path pattern"
