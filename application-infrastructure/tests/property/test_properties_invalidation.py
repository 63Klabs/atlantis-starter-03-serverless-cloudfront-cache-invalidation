"""Property-based tests for CloudFront invalidation client."""

import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from hypothesis import given, settings, strategies as st
from botocore.exceptions import ClientError
from processor.invalidation_client import create_invalidation, generate_caller_reference


# Custom strategies for generating test data

@st.composite
def distribution_id_strategy(draw):
    """Generate valid CloudFront distribution IDs."""
    # CloudFront distribution IDs are alphanumeric strings, typically 13-14 chars
    # Example: E1234ABCDEFGHI
    length = draw(st.integers(min_value=10, max_value=20))
    return draw(st.text(
        min_size=length,
        max_size=length,
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    ))


@st.composite
def path_strategy(draw):
    """Generate valid CloudFront invalidation paths."""
    # Paths must start with /
    # Can contain alphanumeric, hyphens, underscores, dots, wildcards
    # Examples: /*, /images/*, /prod/public/*, /file.jpg
    
    # Choose path type
    path_type = draw(st.sampled_from(['wildcard_root', 'wildcard_dir', 'specific_file', 'nested_path']))
    
    if path_type == 'wildcard_root':
        return '/*'
    
    elif path_type == 'wildcard_dir':
        # Generate directory path with wildcard
        segments = draw(st.integers(min_value=1, max_value=5))
        path_parts = []
        for _ in range(segments):
            segment = draw(st.text(
                min_size=1,
                max_size=20,
                alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_'
            ))
            path_parts.append(segment)
        return '/' + '/'.join(path_parts) + '/*'
    
    elif path_type == 'specific_file':
        # Generate specific file path
        segments = draw(st.integers(min_value=1, max_value=5))
        path_parts = []
        for _ in range(segments):
            segment = draw(st.text(
                min_size=1,
                max_size=20,
                alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_'
            ))
            path_parts.append(segment)
        
        # Add file extension
        extension = draw(st.sampled_from(['jpg', 'png', 'css', 'js', 'html', 'json', 'txt']))
        filename = draw(st.text(
            min_size=1,
            max_size=20,
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_'
        ))
        path_parts.append(f"{filename}.{extension}")
        
        return '/' + '/'.join(path_parts)
    
    else:  # nested_path
        # Generate nested directory path
        segments = draw(st.integers(min_value=2, max_value=6))
        path_parts = []
        for _ in range(segments):
            segment = draw(st.text(
                min_size=1,
                max_size=20,
                alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_'
            ))
            path_parts.append(segment)
        return '/' + '/'.join(path_parts)


@st.composite
def path_list_strategy(draw):
    """Generate a list of valid invalidation paths."""
    # Generate between 1 and 100 paths (well under the 1000 limit)
    num_paths = draw(st.integers(min_value=1, max_value=100))
    paths = []
    for _ in range(num_paths):
        path = draw(path_strategy())
        paths.append(path)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_paths = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)
    
    return unique_paths


# Property Tests

@settings(max_examples=100)
@given(distribution_id_strategy(), path_list_strategy())
def test_property_25_create_invalidation_api_call_correctness(distribution_id, paths):
    """Property 25: CreateInvalidation API call correctness.
    
    For any validated distribution and consolidated path list, the CreateInvalidation
    request should include the distribution ID and the exact consolidated paths.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 25: CreateInvalidation API call correctness**
    **Validates: Requirements 10.1**
    """
    # Mock the CloudFront client
    with patch('processor.invalidation_client.cloudfront_client') as mock_cf:
        # Mock successful response
        mock_invalidation_id = 'I1234567890ABCD'
        mock_cf.create_invalidation.return_value = {
            'Invalidation': {
                'Id': mock_invalidation_id,
                'Status': 'InProgress',
                'CreateTime': datetime.now(timezone.utc)
            }
        }
        
        # Call create_invalidation
        result = create_invalidation(distribution_id, paths)
        
        # Property: The API should be called with the correct distribution ID
        assert mock_cf.create_invalidation.called, \
            "Expected create_invalidation to be called"
        
        call_args = mock_cf.create_invalidation.call_args
        
        # Verify distribution ID
        assert call_args[1]['DistributionId'] == distribution_id, \
            f"Expected DistributionId to be '{distribution_id}', got '{call_args[1]['DistributionId']}'"
        
        # Verify paths are included correctly
        invalidation_batch = call_args[1]['InvalidationBatch']
        assert 'Paths' in invalidation_batch, \
            "Expected InvalidationBatch to contain 'Paths'"
        
        paths_config = invalidation_batch['Paths']
        assert paths_config['Quantity'] == len(paths), \
            f"Expected Quantity to be {len(paths)}, got {paths_config['Quantity']}"
        
        assert paths_config['Items'] == paths, \
            f"Expected Items to be {paths}, got {paths_config['Items']}"
        
        # Verify CallerReference is present and unique
        assert 'CallerReference' in invalidation_batch, \
            "Expected InvalidationBatch to contain 'CallerReference'"
        
        caller_reference = invalidation_batch['CallerReference']
        assert isinstance(caller_reference, str) and len(caller_reference) > 0, \
            f"Expected CallerReference to be a non-empty string, got '{caller_reference}'"
        
        # Verify result contains expected fields
        assert result is not None, \
            "Expected create_invalidation to return a result"
        
        assert result['Id'] == mock_invalidation_id, \
            f"Expected Id to be '{mock_invalidation_id}', got '{result['Id']}'"
        
        assert 'Status' in result, \
            "Expected result to contain 'Status'"
        
        assert 'CreateTime' in result, \
            "Expected result to contain 'CreateTime'"


@settings(max_examples=100)
@given(distribution_id_strategy(), path_list_strategy())
def test_property_25_caller_reference_uniqueness(distribution_id, paths):
    """Property 25 (variant): CallerReference is unique for each request.
    
    For any two consecutive invalidation requests, the CallerReference should
    be different to ensure uniqueness.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 25: CreateInvalidation API call correctness**
    **Validates: Requirements 10.1**
    """
    # Mock the CloudFront client
    with patch('processor.invalidation_client.cloudfront_client') as mock_cf:
        # Mock successful response
        mock_cf.create_invalidation.return_value = {
            'Invalidation': {
                'Id': 'I1234567890ABCD',
                'Status': 'InProgress',
                'CreateTime': datetime.now(timezone.utc)
            }
        }
        
        # Call create_invalidation twice
        create_invalidation(distribution_id, paths)
        create_invalidation(distribution_id, paths)
        
        # Get the CallerReferences from both calls
        assert mock_cf.create_invalidation.call_count == 2, \
            "Expected create_invalidation to be called twice"
        
        first_call = mock_cf.create_invalidation.call_args_list[0]
        second_call = mock_cf.create_invalidation.call_args_list[1]
        
        first_caller_ref = first_call[1]['InvalidationBatch']['CallerReference']
        second_caller_ref = second_call[1]['InvalidationBatch']['CallerReference']
        
        # Property: CallerReferences should be different
        assert first_caller_ref != second_caller_ref, \
            f"Expected CallerReferences to be unique, but both were '{first_caller_ref}'"


@settings(max_examples=100)
@given(distribution_id_strategy())
def test_property_25_empty_paths_handled_correctly(distribution_id):
    """Property 25 (variant): Empty path lists are handled gracefully.
    
    For any distribution with an empty path list, create_invalidation should
    return None without making an API call.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 25: CreateInvalidation API call correctness**
    **Validates: Requirements 10.1**
    """
    # Mock the CloudFront client
    with patch('processor.invalidation_client.cloudfront_client') as mock_cf:
        # Call create_invalidation with empty paths
        result = create_invalidation(distribution_id, [])
        
        # Property: Should return None for empty paths
        assert result is None, \
            f"Expected None for empty paths, got {result}"
        
        # Property: Should not call the API
        assert not mock_cf.create_invalidation.called, \
            "Expected create_invalidation not to be called with empty paths"


@settings(max_examples=100)
@given(distribution_id_strategy(), path_list_strategy())
def test_property_25_retry_on_throttling(distribution_id, paths):
    """Property 25 (variant): Retries on throttling errors.
    
    For any invalidation request that encounters throttling, the client should
    retry with exponential backoff.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 25: CreateInvalidation API call correctness**
    **Validates: Requirements 10.3**
    """
    # Mock the CloudFront client
    with patch('processor.invalidation_client.cloudfront_client') as mock_cf:
        # First call fails with throttling, second succeeds
        error_response = {
            'Error': {
                'Code': 'TooManyInvalidationsInProgress',
                'Message': 'Too many invalidations in progress'
            }
        }
        
        mock_cf.create_invalidation.side_effect = [
            ClientError(error_response, 'CreateInvalidation'),
            {
                'Invalidation': {
                    'Id': 'I1234567890ABCD',
                    'Status': 'InProgress',
                    'CreateTime': datetime.now(timezone.utc)
                }
            }
        ]
        
        # Call create_invalidation (should retry and succeed)
        result = create_invalidation(distribution_id, paths)
        
        # Property: Should eventually succeed after retry
        assert result is not None, \
            "Expected create_invalidation to succeed after retry"
        
        # Property: Should have been called twice (initial + 1 retry)
        assert mock_cf.create_invalidation.call_count == 2, \
            f"Expected 2 calls (initial + retry), got {mock_cf.create_invalidation.call_count}"


@settings(max_examples=10, deadline=None)
@given(distribution_id_strategy(), path_list_strategy())
def test_property_25_failure_after_max_retries(distribution_id, paths):
    """Property 25 (variant): Raises exception after max retries.
    
    For any invalidation request that fails repeatedly, the client should
    raise an exception after exhausting all retry attempts.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 25: CreateInvalidation API call correctness**
    **Validates: Requirements 10.4**
    """
    # Mock the CloudFront client
    with patch('processor.invalidation_client.cloudfront_client') as mock_cf:
        # All calls fail with service error
        error_response = {
            'Error': {
                'Code': 'ServiceUnavailable',
                'Message': 'Service temporarily unavailable'
            }
        }
        
        mock_cf.create_invalidation.side_effect = ClientError(
            error_response,
            'CreateInvalidation'
        )
        
        # Call create_invalidation (should fail after retries)
        try:
            create_invalidation(distribution_id, paths)
            assert False, "Expected ClientError to be raised after max retries"
        except ClientError as e:
            # Property: Should raise ClientError after exhausting retries
            assert e.response['Error']['Code'] == 'ServiceUnavailable', \
                f"Expected ServiceUnavailable error, got {e.response['Error']['Code']}"
        
        # Property: Should have attempted max retries (5 attempts)
        assert mock_cf.create_invalidation.call_count == 5, \
            f"Expected 5 attempts (max retries), got {mock_cf.create_invalidation.call_count}"


def test_property_25_caller_reference_format():
    """Property 25 (variant): CallerReference has expected format.
    
    For any generated CallerReference, it should contain a timestamp and UUID
    component separated by a hyphen.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 25: CreateInvalidation API call correctness**
    **Validates: Requirements 10.1**
    """
    # Generate multiple caller references
    caller_refs = [generate_caller_reference() for _ in range(10)]
    
    for caller_ref in caller_refs:
        # Property: Should be a non-empty string
        assert isinstance(caller_ref, str) and len(caller_ref) > 0, \
            f"Expected non-empty string, got '{caller_ref}'"
        
        # Property: Should contain a hyphen separator
        assert '-' in caller_ref, \
            f"Expected CallerReference to contain hyphen, got '{caller_ref}'"
        
        # Property: Should have timestamp and UUID parts
        parts = caller_ref.split('-')
        assert len(parts) >= 2, \
            f"Expected at least 2 parts (timestamp-uuid), got {len(parts)} parts in '{caller_ref}'"
        
        # Property: First part should be numeric timestamp (14+ digits)
        timestamp_part = parts[0]
        assert timestamp_part.isdigit(), \
            f"Expected timestamp part to be numeric, got '{timestamp_part}'"
        
        assert len(timestamp_part) >= 14, \
            f"Expected timestamp to be at least 14 digits, got {len(timestamp_part)} in '{timestamp_part}'"
    
    # Property: All generated references should be unique
    assert len(caller_refs) == len(set(caller_refs)), \
        f"Expected all CallerReferences to be unique, got duplicates in {caller_refs}"


# Property 26: Successful invalidation logging

@settings(max_examples=100)
@given(distribution_id_strategy(), path_list_strategy())
def test_property_26_successful_invalidation_logging(distribution_id, paths):
    """Property 26: Successful invalidation logging.
    
    For any successful CreateInvalidation response, the log output should be
    valid JSON containing the invalidation ID and status.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 26: Successful invalidation logging**
    **Validates: Requirements 10.2**
    """
    # Mock the CloudFront client
    with patch('processor.invalidation_client.cloudfront_client') as mock_cf:
        # Mock successful response
        mock_invalidation_id = 'I1234567890ABCD'
        mock_status = 'InProgress'
        mock_create_time = datetime.now(timezone.utc)
        
        mock_cf.create_invalidation.return_value = {
            'Invalidation': {
                'Id': mock_invalidation_id,
                'Status': mock_status,
                'CreateTime': mock_create_time
            }
        }
        
        # Capture log output
        with patch('processor.invalidation_client.logger') as mock_logger:
            # Call create_invalidation
            result = create_invalidation(distribution_id, paths)
            
            # Property: Should log success with info level
            assert mock_logger.info.called, \
                "Expected logger.info to be called for successful invalidation"
            
            # Get the log calls
            info_calls = mock_logger.info.call_args_list
            
            # Property: Should have at least one info log call
            assert len(info_calls) > 0, \
                "Expected at least one info log call"
            
            # Find the success log call (contains "Successfully created invalidation")
            success_log_found = False
            for call in info_calls:
                message = call[0][0] if call[0] else ""
                if "Successfully created invalidation" in message:
                    success_log_found = True
                    
                    # Property: Log should contain extra_fields with required information
                    if 'extra' in call[1]:
                        extra_fields = call[1]['extra'].get('extra_fields', {})
                        
                        # Property: Should log distribution_id
                        assert 'distribution_id' in extra_fields, \
                            "Expected 'distribution_id' in log extra_fields"
                        assert extra_fields['distribution_id'] == distribution_id, \
                            f"Expected distribution_id '{distribution_id}', got '{extra_fields['distribution_id']}'"
                        
                        # Property: Should log invalidation_id
                        assert 'invalidation_id' in extra_fields, \
                            "Expected 'invalidation_id' in log extra_fields"
                        assert extra_fields['invalidation_id'] == mock_invalidation_id, \
                            f"Expected invalidation_id '{mock_invalidation_id}', got '{extra_fields['invalidation_id']}'"
                        
                        # Property: Should log status
                        assert 'status' in extra_fields, \
                            "Expected 'status' in log extra_fields"
                        assert extra_fields['status'] == mock_status, \
                            f"Expected status '{mock_status}', got '{extra_fields['status']}'"
                    
                    break
            
            # Property: Success log should be present
            assert success_log_found, \
                "Expected to find success log message containing 'Successfully created invalidation'"


@settings(max_examples=100)
@given(distribution_id_strategy(), path_list_strategy())
def test_property_26_json_log_format_validity(distribution_id, paths):
    """Property 26 (variant): JSON log format validity.
    
    For any log message produced during invalidation, the message should be
    valid JSON that can be parsed without errors.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 26: Successful invalidation logging**
    **Validates: Requirements 13.3**
    """
    import json
    import io
    import sys
    
    # Mock the CloudFront client
    with patch('processor.invalidation_client.cloudfront_client') as mock_cf:
        # Mock successful response
        mock_cf.create_invalidation.return_value = {
            'Invalidation': {
                'Id': 'I1234567890ABCD',
                'Status': 'InProgress',
                'CreateTime': datetime.now(timezone.utc)
            }
        }
        
        # Capture stdout to check JSON format
        captured_output = io.StringIO()
        
        # Temporarily replace stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output
        
        try:
            # Call create_invalidation
            result = create_invalidation(distribution_id, paths)
            
            # Restore stdout
            sys.stdout = old_stdout
            
            # Get the captured output
            log_output = captured_output.getvalue()
            
            # Property: Each line should be valid JSON
            if log_output.strip():
                for line in log_output.strip().split('\n'):
                    if line.strip():
                        try:
                            log_entry = json.loads(line)
                            
                            # Property: Should have standard log fields
                            assert 'timestamp' in log_entry or 'level' in log_entry or 'message' in log_entry, \
                                f"Expected log entry to have standard fields, got {log_entry.keys()}"
                        
                        except json.JSONDecodeError as e:
                            assert False, f"Expected valid JSON log output, but got JSONDecodeError: {e}\nLine: {line}"
        
        finally:
            # Ensure stdout is restored
            sys.stdout = old_stdout


@settings(max_examples=10, deadline=None)
@given(distribution_id_strategy(), path_list_strategy())
def test_property_26_error_logging_on_failure(distribution_id, paths):
    """Property 26 (variant): Error logging on failure.
    
    For any failed CreateInvalidation request, the log output should contain
    error information including error code and message.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 26: Successful invalidation logging**
    **Validates: Requirements 10.4**
    """
    # Mock the CloudFront client
    with patch('processor.invalidation_client.cloudfront_client') as mock_cf:
        # Mock error response
        error_code = 'TooManyInvalidationsInProgress'
        error_message = 'Too many invalidations in progress'
        error_response = {
            'Error': {
                'Code': error_code,
                'Message': error_message
            }
        }
        
        mock_cf.create_invalidation.side_effect = ClientError(
            error_response,
            'CreateInvalidation'
        )
        
        # Capture log output
        with patch('processor.invalidation_client.logger') as mock_logger:
            # Call create_invalidation (should fail and retry)
            try:
                create_invalidation(distribution_id, paths)
            except ClientError:
                pass  # Expected to fail
            
            # Property: Should log error with error level
            assert mock_logger.error.called, \
                "Expected logger.error to be called for failed invalidation"
            
            # Get the error log calls
            error_calls = mock_logger.error.call_args_list
            
            # Property: Should have at least one error log call
            assert len(error_calls) > 0, \
                "Expected at least one error log call"
            
            # Check the last error call (final failure)
            last_error_call = error_calls[-1]
            message = last_error_call[0][0] if last_error_call[0] else ""
            
            # Property: Error message should contain distribution ID
            assert distribution_id in message, \
                f"Expected error message to contain distribution_id '{distribution_id}'"
            
            # Property: Should log extra_fields with error information
            if 'extra' in last_error_call[1]:
                extra_fields = last_error_call[1]['extra'].get('extra_fields', {})
                
                # Property: Should log error_code
                assert 'error_code' in extra_fields, \
                    "Expected 'error_code' in error log extra_fields"
                assert extra_fields['error_code'] == error_code, \
                    f"Expected error_code '{error_code}', got '{extra_fields['error_code']}'"
                
                # Property: Should log error_message
                assert 'error_message' in extra_fields, \
                    "Expected 'error_message' in error log extra_fields"
                assert extra_fields['error_message'] == error_message, \
                    f"Expected error_message '{error_message}', got '{extra_fields['error_message']}'"
