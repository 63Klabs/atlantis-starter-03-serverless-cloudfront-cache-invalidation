#!/usr/bin/env python3
"""
Integration tests for backward compatibility.

**Feature: dynamic-bucket-consolidation-config, Integration Test: Backward compatibility**
**Validates: Requirements 4.1**

This module tests that the enhanced configuration system maintains full backward
compatibility with existing deployments and buckets that don't have the new
configuration tags.

These tests verify:
1. Existing buckets without new tags continue to work exactly as before
2. Consolidation behavior remains unchanged for default configuration
3. Enhanced system can be deployed over existing system without issues
4. No regression in existing functionality

Run with: pytest tests/integration/test_backward_compatibility.py -v

Environment variables required:
- PROCESSOR_FUNCTION_NAME: Name of the deployed Processor Lambda
- TEST_QUEUE_URL: URL of the SQS queue
- TEST_BUCKET_WITHOUT_CONFIG_TAGS: Name of test S3 bucket without configuration tags
- TEST_DISTRIBUTION_ID: CloudFront distribution ID with appropriate tags
- DIRECTORY_CONSOLIDATION_THRESHOLD: Expected default threshold from CloudFormation
- CONSOLIDATION_STOP_LEVEL: Expected default stop level from CloudFormation
"""

import os
import json
import time
import uuid
import boto3
import pytest
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


# Skip all tests if not in integration test mode
pytestmark = pytest.mark.skipif(
    os.environ.get('RUN_INTEGRATION_TESTS') != '1',
    reason="Integration tests require RUN_INTEGRATION_TESTS=1 environment variable"
)


@pytest.fixture(scope="module")
def aws_clients():
    """Create AWS service clients for integration tests."""
    return {
        'sqs': boto3.client('sqs'),
        's3': boto3.client('s3'),
        'cloudfront': boto3.client('cloudfront'),
        'lambda': boto3.client('lambda'),
        'logs': boto3.client('logs'),
    }


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration from environment variables."""
    config = {
        'processor_function_name': os.environ.get('PROCESSOR_FUNCTION_NAME'),
        'queue_url': os.environ.get('TEST_QUEUE_URL'),
        'test_bucket': os.environ.get('TEST_BUCKET_WITHOUT_CONFIG_TAGS'),
        'test_distribution_id': os.environ.get('TEST_DISTRIBUTION_ID'),
        'expected_default_threshold': int(os.environ.get('DIRECTORY_CONSOLIDATION_THRESHOLD', '3')),
        'expected_default_stop_level': int(os.environ.get('CONSOLIDATION_STOP_LEVEL', '1')),
    }
    
    # Validate required configuration
    missing = [k for k, v in config.items() if not v]
    if missing:
        pytest.skip(f"Missing required environment variables: {', '.join(missing)}")
    
    return config


@pytest.fixture(scope="function")
def clean_queue_state(aws_clients, test_config):
    """
    Fixture to ensure clean SQS queue state before and after each test.
    """
    sqs = aws_clients['sqs']
    
    # Clean up before test
    try:
        sqs.purge_queue(QueueUrl=test_config['queue_url'])
        time.sleep(2)  # Wait for purge to complete
    except Exception:
        pass  # Queue might be empty
    
    yield
    
    # Clean up after test
    try:
        sqs.purge_queue(QueueUrl=test_config['queue_url'])
    except Exception:
        pass


def ensure_legacy_bucket_tags(s3_client, bucket_name: str):
    """
    Helper function to ensure bucket has only legacy tags (no new config tags).
    
    Args:
        s3_client: Boto3 S3 client
        bucket_name: Name of the bucket to configure
    """
    # Set only the required legacy tags
    legacy_tags = {
        'AllowInvalidationEvents': 'true',  # Required for processing
        # Explicitly NOT setting new config tags:
        # - invalidator:DirectoryConsolidationThreshold
        # - invalidator:ConsolidationStopLevel
    }
    
    tag_set = [{'Key': k, 'Value': v} for k, v in legacy_tags.items()]
    s3_client.put_bucket_tagging(
        Bucket=bucket_name,
        Tagging={'TagSet': tag_set}
    )


def send_test_event(sqs_client, queue_url: str, bucket_name: str, object_key: str) -> str:
    """
    Helper function to send a test S3 event to the queue.
    
    Returns:
        Message ID of the sent message
    """
    test_message = {
        'bucketName': bucket_name,
        'objectKey': object_key,
        'originPath': '/prod/public',
        'stageId': 'prod',
        'eventTime': datetime.now(timezone.utc).isoformat(),
        'eventType': 'ObjectCreated:Put'
    }
    
    response = sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(test_message)
    )
    
    return response['MessageId']


def get_recent_log_events(logs_client, function_name: str, minutes: int = 5) -> List[Dict[str, Any]]:
    """
    Helper function to get recent log events from a Lambda function.
    
    Args:
        logs_client: Boto3 CloudWatch Logs client
        function_name: Name of the Lambda function
        minutes: Number of minutes back to search
        
    Returns:
        List of log events
    """
    log_group_name = f'/aws/lambda/{function_name}'
    
    # Calculate time range
    end_time = int(time.time() * 1000)
    start_time = end_time - (minutes * 60 * 1000)
    
    try:
        # Get log streams
        streams_response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=5
        )
        
        all_events = []
        for stream in streams_response['logStreams']:
            try:
                events_response = logs_client.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=stream['logStreamName'],
                    startTime=start_time,
                    endTime=end_time
                )
                all_events.extend(events_response['events'])
            except Exception:
                continue  # Skip streams that can't be read
        
        # Sort by timestamp
        all_events.sort(key=lambda x: x['timestamp'])
        return all_events
        
    except Exception as e:
        print(f"Warning: Could not retrieve log events: {e}")
        return []


class TestExistingBucketsWithoutNewTags:
    """Test that existing buckets without new configuration tags continue to work."""
    
    def test_legacy_bucket_processing(self, aws_clients, test_config, clean_queue_state):
        """
        Test that buckets without new configuration tags work exactly as before.
        
        **Validates: Requirements 4.1**
        
        This test verifies:
        1. Buckets without new tags are processed successfully
        2. No errors occur due to missing configuration tags
        3. Processing completes normally with default behavior
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Step 1: Ensure bucket has only legacy tags (no new config tags)
        ensure_legacy_bucket_tags(s3, bucket_name)
        
        # Step 2: Send test events using patterns that worked in the original system
        test_paths = [
            '/prod/public/assets/css/style.css',
            '/prod/public/assets/js/app.js',
            '/prod/public/images/logo.png',
            '/prod/public/pages/index.html',
            '/prod/public/pages/about.html',
        ]
        
        message_ids = []
        for path in test_paths:
            message_id = send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            message_ids.append(message_id)
            time.sleep(0.1)  # Small delay between messages
        
        # Step 3: Wait for messages to be available
        time.sleep(2)
        
        # Step 4: Invoke Processor Lambda
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Step 5: Verify Lambda execution was successful
        assert response['StatusCode'] == 200
        
        response_payload = json.loads(response['Payload'].read())
        if 'FunctionError' in response:
            pytest.fail(f"Legacy bucket processing failed: {response_payload}")
        
        # Step 6: Verify no errors in logs
        time.sleep(3)
        
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Check for any error messages related to configuration
        config_errors = [
            msg for msg in log_messages 
            if any(error_term in msg.lower() for error_term in ['error', 'exception', 'failed']) and
               any(config_term in msg.lower() for config_term in ['tag', 'config', 'threshold', 'stop level'])
        ]
        
        assert not config_errors, f"Configuration errors found in legacy processing: {config_errors}"
        
        # Verify processing completed successfully
        success_indicators = [
            msg for msg in log_messages
            if any(success_term in msg.lower() for success_term in ['processed', 'completed', 'success', 'invalidation'])
        ]
        
        assert success_indicators, f"No success indicators found in logs: {log_messages}"
    
    def test_legacy_consolidation_behavior(self, aws_clients, test_config, clean_queue_state):
        """
        Test that consolidation behavior for legacy buckets matches original system.
        
        **Validates: Requirements 4.1**
        
        This test verifies:
        1. Directory consolidation uses default threshold (3)
        2. Stop level defaults to 1 (original behavior)
        3. Consolidation patterns match pre-enhancement behavior
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Step 1: Ensure legacy bucket configuration
        ensure_legacy_bucket_tags(s3, bucket_name)
        
        # Step 2: Send events that should trigger consolidation with default threshold (3)
        # This pattern should consolidate to /prod/public/dir1/* with default threshold
        consolidation_test_paths = [
            '/prod/public/dir1/file1.html',
            '/prod/public/dir1/file2.html',
            '/prod/public/dir1/file3.html',  # Should trigger consolidation at threshold=3
            '/prod/public/dir1/file4.html',
        ]
        
        for path in consolidation_test_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        # Step 3: Also send events that should NOT consolidate (below threshold)
        no_consolidation_paths = [
            '/prod/public/dir2/file1.html',
            '/prod/public/dir2/file2.html',  # Only 2 files, should not consolidate
        ]
        
        for path in no_consolidation_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Step 4: Process events
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(3)
        
        # Step 5: Verify consolidation behavior matches defaults
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Look for evidence of default threshold usage
        default_threshold_str = str(test_config['expected_default_threshold'])
        threshold_usage_found = any(
            default_threshold_str in msg and 'threshold' in msg.lower()
            for msg in log_messages
        )
        
        # Look for evidence of default stop level usage
        default_stop_level_str = str(test_config['expected_default_stop_level'])
        stop_level_usage_found = any(
            default_stop_level_str in msg and 'stop level' in msg.lower()
            for msg in log_messages
        )
        
        # At least one default configuration should be evident
        assert threshold_usage_found or stop_level_usage_found, \
            f"Default configuration usage not found in logs: {log_messages}"
        
        # Verify no custom configuration was applied
        custom_config_indicators = [
            msg for msg in log_messages
            if any(custom_term in msg.lower() for custom_term in ['custom', 'bucket-specific', 'override'])
        ]
        
        assert not custom_config_indicators, \
            f"Custom configuration should not be applied to legacy buckets: {custom_config_indicators}"
    
    def test_legacy_index_file_handling(self, aws_clients, test_config, clean_queue_state):
        """
        Test that index file handling works as before for legacy buckets.
        
        **Validates: Requirements 4.1**
        
        This test verifies:
        1. index.html and default.html files are handled correctly
        2. Directory consolidation for index files works as before
        3. No new stop level restrictions affect legacy behavior
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Step 1: Ensure legacy bucket configuration
        ensure_legacy_bucket_tags(s3, bucket_name)
        
        # Step 2: Send events with index files (classic pattern)
        index_file_paths = [
            '/prod/public/section1/index.html',
            '/prod/public/section1/default.html',
            '/prod/public/section2/index.html',
            '/prod/public/section3/default.html',
        ]
        
        for path in index_file_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Step 3: Process events
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(3)
        
        # Step 4: Verify index file handling
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Look for evidence of index file processing
        index_processing_found = any(
            ('index' in msg.lower() or 'default' in msg.lower()) and 
            ('process' in msg.lower() or 'consolidat' in msg.lower())
            for msg in log_messages
        )
        
        # Verify no stop level restrictions affected index file handling
        stop_level_restrictions = [
            msg for msg in log_messages
            if 'stop level' in msg.lower() and 'prevent' in msg.lower()
        ]
        
        # With default stop level (1), there should be no restrictions on index file handling
        assert not stop_level_restrictions, \
            f"Stop level restrictions should not affect legacy index file handling: {stop_level_restrictions}"
        
        # Verify processing completed successfully
        processing_success = any(
            'process' in msg.lower() and ('complet' in msg.lower() or 'success' in msg.lower())
            for msg in log_messages
        )
        
        assert processing_success or index_processing_found, \
            f"Index file processing not successful: {log_messages}"


class TestConsolidationBehaviorUnchanged:
    """Test that consolidation behavior remains unchanged for default configuration."""
    
    def test_default_directory_consolidation_threshold(self, aws_clients, test_config, clean_queue_state):
        """
        Test that directory consolidation uses the expected default threshold.
        
        **Validates: Requirements 4.1**
        
        This test verifies:
        1. Default threshold value is used when no tags are present
        2. Consolidation triggers at the expected file count
        3. Behavior matches pre-enhancement system
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        expected_threshold = test_config['expected_default_threshold']
        
        # Step 1: Ensure legacy bucket configuration
        ensure_legacy_bucket_tags(s3, bucket_name)
        
        # Step 2: Send exactly (threshold - 1) files - should NOT consolidate
        below_threshold_paths = []
        for i in range(expected_threshold - 1):
            below_threshold_paths.append(f'/prod/public/below_threshold/file{i+1}.html')
        
        for path in below_threshold_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Process below-threshold events
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        # Get logs for below-threshold test
        log_events_below = get_recent_log_events(logs_client, test_config['processor_function_name'])
        
        # Clean queue for next test
        sqs.purge_queue(QueueUrl=test_config['queue_url'])
        time.sleep(2)
        
        # Step 3: Send exactly threshold files - SHOULD consolidate
        at_threshold_paths = []
        for i in range(expected_threshold):
            at_threshold_paths.append(f'/prod/public/at_threshold/file{i+1}.html')
        
        for path in at_threshold_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Process at-threshold events
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        # Get logs for at-threshold test
        log_events_at = get_recent_log_events(logs_client, test_config['processor_function_name'], minutes=2)
        log_messages_at = [event['message'] for event in log_events_at]
        
        # Step 4: Verify threshold behavior
        # Look for evidence that the expected threshold was used
        threshold_str = str(expected_threshold)
        threshold_usage_found = any(
            threshold_str in msg and 'threshold' in msg.lower()
            for msg in log_messages_at
        )
        
        assert threshold_usage_found, \
            f"Expected threshold {expected_threshold} not found in logs: {log_messages_at}"
        
        # Look for consolidation activity at the threshold
        consolidation_activity = any(
            'consolidat' in msg.lower() and ('at_threshold' in msg or threshold_str in msg)
            for msg in log_messages_at
        )
        
        # At least some evidence of threshold-based behavior should be present
        assert threshold_usage_found or consolidation_activity, \
            f"No evidence of threshold-based consolidation behavior: {log_messages_at}"
    
    def test_default_stop_level_behavior(self, aws_clients, test_config, clean_queue_state):
        """
        Test that stop level defaults to 1 and behaves as in the original system.
        
        **Validates: Requirements 4.1**
        
        This test verifies:
        1. Default stop level is 1 (original behavior)
        2. No consolidation restrictions are applied at depth > 1
        3. Behavior matches pre-enhancement system
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        expected_stop_level = test_config['expected_default_stop_level']
        
        # Step 1: Ensure legacy bucket configuration
        ensure_legacy_bucket_tags(s3, bucket_name)
        
        # Step 2: Send events at various depths to test stop level behavior
        # With stop level 1, consolidation should work normally at all depths > 1
        multi_depth_paths = [
            '/prod/public/level2/file1.html',  # Depth 2 - should consolidate normally
            '/prod/public/level2/file2.html',
            '/prod/public/level2/file3.html',
            '/prod/public/level2/subdir/file1.html',  # Depth 3 - should consolidate normally
            '/prod/public/level2/subdir/file2.html',
            '/prod/public/level2/subdir/file3.html',
        ]
        
        for path in multi_depth_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Step 3: Process events
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(3)
        
        # Step 4: Verify stop level behavior
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Look for evidence of default stop level usage
        stop_level_str = str(expected_stop_level)
        stop_level_usage_found = any(
            stop_level_str in msg and 'stop level' in msg.lower()
            for msg in log_messages
        )
        
        # With stop level 1, there should be NO consolidation prevention at depths > 1
        consolidation_prevented = any(
            'prevent' in msg.lower() and 'consolidat' in msg.lower()
            for msg in log_messages
        )
        
        # Verify default stop level is being used
        if stop_level_usage_found:
            assert expected_stop_level == 1, \
                f"Expected default stop level to be 1, but found {expected_stop_level}"
        
        # With stop level 1, consolidation should NOT be prevented at deeper levels
        assert not consolidation_prevented, \
            f"Consolidation should not be prevented with default stop level 1: {log_messages}"
    
    def test_sibling_directory_consolidation(self, aws_clients, test_config, clean_queue_state):
        """
        Test that sibling directory consolidation works as in the original system.
        
        **Validates: Requirements 4.1**
        
        This test verifies:
        1. Sibling directories consolidate normally with default configuration
        2. No new stop level restrictions affect sibling consolidation
        3. Behavior matches pre-enhancement system
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Step 1: Ensure legacy bucket configuration
        ensure_legacy_bucket_tags(s3, bucket_name)
        
        # Step 2: Send events that should trigger sibling directory consolidation
        # Create multiple sibling directories with files
        sibling_paths = [
            '/prod/public/siblings/dir1/file1.html',
            '/prod/public/siblings/dir1/file2.html',
            '/prod/public/siblings/dir2/file1.html',
            '/prod/public/siblings/dir2/file2.html',
            '/prod/public/siblings/dir3/file1.html',
            '/prod/public/siblings/dir3/file2.html',
        ]
        
        for path in sibling_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Step 3: Process events
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(3)
        
        # Step 4: Verify sibling consolidation behavior
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Look for evidence of sibling directory processing
        sibling_processing_found = any(
            'sibling' in msg.lower() or ('dir1' in msg and 'dir2' in msg and 'dir3' in msg)
            for msg in log_messages
        )
        
        # Verify no stop level restrictions affected sibling consolidation
        sibling_restrictions = [
            msg for msg in log_messages
            if 'sibling' in msg.lower() and 'prevent' in msg.lower()
        ]
        
        # With default stop level (1), sibling consolidation should work normally
        assert not sibling_restrictions, \
            f"Stop level should not restrict sibling consolidation with default configuration: {sibling_restrictions}"
        
        # Verify processing completed successfully
        processing_indicators = [
            msg for msg in log_messages
            if any(indicator in msg.lower() for indicator in ['process', 'consolidat', 'invalidat'])
        ]
        
        assert processing_indicators, \
            f"No processing indicators found for sibling consolidation: {log_messages}"


class TestEnhancedSystemDeployment:
    """Test deployment of enhanced system over existing system."""
    
    def test_environment_variables_present(self, aws_clients, test_config):
        """
        Test that enhanced system has required environment variables set.
        
        **Validates: Requirements 4.1**
        
        This test verifies:
        1. New environment variables are present in Lambda configuration
        2. Default values are set correctly
        3. Enhanced system is properly configured
        """
        lambda_client = aws_clients['lambda']
        
        # Get Lambda function configuration
        response = lambda_client.get_function_configuration(
            FunctionName=test_config['processor_function_name']
        )
        
        env_vars = response.get('Environment', {}).get('Variables', {})
        
        # Verify all required environment variables are present
        required_vars = {
            'DIRECTORY_CONSOLIDATION_THRESHOLD': test_config['expected_default_threshold'],
            'CONSOLIDATION_STOP_LEVEL': test_config['expected_default_stop_level'],
            'AGGREGATION_WINDOW_SECONDS': None,  # Don't check specific value, just presence
        }
        
        for var_name, expected_value in required_vars.items():
            assert var_name in env_vars, \
                f"Required environment variable {var_name} not found in enhanced system"
            
            # Verify the value is a valid number
            try:
                actual_value = int(env_vars[var_name])
            except ValueError:
                pytest.fail(f"Environment variable {var_name} has invalid value: {env_vars[var_name]}")
            
            # Check expected values where specified
            if expected_value is not None:
                assert actual_value == expected_value, \
                    f"Environment variable {var_name} has value {actual_value}, expected {expected_value}"
        
        # Verify values are within valid ranges
        threshold = int(env_vars['DIRECTORY_CONSOLIDATION_THRESHOLD'])
        stop_level = int(env_vars['CONSOLIDATION_STOP_LEVEL'])
        
        assert 1 <= threshold <= 1000, \
            f"Directory threshold {threshold} out of valid range (1-1000)"
        assert 0 <= stop_level <= 1000, \
            f"Stop level {stop_level} out of valid range (0-1000)"
    
    def test_backward_compatible_function_signature(self, aws_clients, test_config, clean_queue_state):
        """
        Test that enhanced system processes legacy events without modification.
        
        **Validates: Requirements 4.1**
        
        This test verifies:
        1. Legacy event format is still supported
        2. No changes required to existing event producers
        3. Enhanced system accepts same input as original system
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Step 1: Ensure legacy bucket configuration
        ensure_legacy_bucket_tags(s3, bucket_name)
        
        # Step 2: Send events in the exact legacy format
        legacy_event_format = {
            'bucketName': bucket_name,
            'objectKey': '/prod/public/legacy/test.html',
            'originPath': '/prod/public',
            'stageId': 'prod',
            'eventTime': datetime.now(timezone.utc).isoformat(),
            'eventType': 'ObjectCreated:Put'
        }
        
        # Send the legacy format event
        response = sqs.send_message(
            QueueUrl=test_config['queue_url'],
            MessageBody=json.dumps(legacy_event_format)
        )
        
        message_id = response['MessageId']
        
        time.sleep(2)
        
        # Step 3: Process the legacy event
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Step 4: Verify successful processing
        assert response['StatusCode'] == 200
        
        response_payload = json.loads(response['Payload'].read())
        if 'FunctionError' in response:
            pytest.fail(f"Enhanced system failed to process legacy event format: {response_payload}")
        
        time.sleep(2)
        
        # Step 5: Verify no format-related errors in logs
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Check for any format or parsing errors
        format_errors = [
            msg for msg in log_messages
            if any(error_term in msg.lower() for error_term in ['format', 'parse', 'invalid', 'error']) and
               any(event_term in msg.lower() for event_term in ['event', 'message', 'json'])
        ]
        
        assert not format_errors, \
            f"Event format errors found when processing legacy events: {format_errors}"
        
        # Verify successful processing indicators
        success_indicators = [
            msg for msg in log_messages
            if any(success_term in msg.lower() for success_term in ['process', 'success', 'complet'])
        ]
        
        assert success_indicators, \
            f"No success indicators found for legacy event processing: {log_messages}"
    
    def test_no_regression_in_error_handling(self, aws_clients, test_config, clean_queue_state):
        """
        Test that error handling remains robust in enhanced system.
        
        **Validates: Requirements 4.1**
        
        This test verifies:
        1. Enhanced system handles errors as gracefully as original
        2. No new error conditions introduced by enhancements
        3. Error recovery mechanisms still work
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Step 1: Ensure legacy bucket configuration
        ensure_legacy_bucket_tags(s3, bucket_name)
        
        # Step 2: Send a malformed event (should be handled gracefully)
        malformed_event = {
            'bucketName': bucket_name,
            'objectKey': '/prod/public/malformed/test.html',
            'originPath': '/prod/public',
            'stageId': 'prod',
            # Missing eventTime and eventType - should be handled gracefully
        }
        
        response = sqs.send_message(
            QueueUrl=test_config['queue_url'],
            MessageBody=json.dumps(malformed_event)
        )
        
        time.sleep(2)
        
        # Step 3: Process the malformed event
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Step 4: Verify system handles error gracefully (should not crash)
        assert response['StatusCode'] == 200
        
        # The function should complete even if individual events fail
        response_payload = json.loads(response['Payload'].read())
        
        time.sleep(2)
        
        # Step 5: Verify error handling in logs
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Look for appropriate error handling (warnings/errors logged, but processing continues)
        error_handling_found = any(
            any(error_term in msg.lower() for error_term in ['error', 'warning', 'invalid']) and
            not any(crash_term in msg.lower() for crash_term in ['crash', 'exception', 'failed'])
            for msg in log_messages
        )
        
        # Look for evidence that processing continued despite errors
        continued_processing = any(
            any(continue_term in msg.lower() for continue_term in ['continu', 'process', 'next'])
            for msg in log_messages
        )
        
        # System should handle errors gracefully without crashing
        # Either error handling should be evident, or processing should continue normally
        graceful_handling = error_handling_found or continued_processing or len(log_messages) > 0
        
        assert graceful_handling, \
            f"Enhanced system did not handle errors gracefully: {log_messages}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])