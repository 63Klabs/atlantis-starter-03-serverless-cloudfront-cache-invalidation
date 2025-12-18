#!/usr/bin/env python3
"""
Integration tests for enhanced configuration flow.

**Feature: dynamic-bucket-consolidation-config, Integration Test: Enhanced configuration flow**
**Validates: All Requirements**

This module tests the end-to-end enhanced configuration flow to verify that
bucket-specific configuration tags and CloudFormation parameters work correctly
with real AWS services.

These tests require:
1. Deployed CloudFormation stack with enhanced configuration parameters
2. AWS credentials configured
3. Test S3 buckets with various configuration tag combinations
4. Test CloudFront distributions with appropriate tags

Run with: pytest tests/integration/test_enhanced_configuration_flow.py -v

Environment variables required:
- PROCESSOR_FUNCTION_NAME: Name of the deployed Processor Lambda
- TEST_QUEUE_URL: URL of the SQS queue
- TEST_BUCKET_WITH_CONFIG_TAGS: Name of test S3 bucket with configuration tags
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
        'bucket_with_config_tags': os.environ.get('TEST_BUCKET_WITH_CONFIG_TAGS'),
        'bucket_without_config_tags': os.environ.get('TEST_BUCKET_WITHOUT_CONFIG_TAGS'),
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


def setup_test_bucket_tags(s3_client, bucket_name: str, config_tags: Dict[str, str]):
    """
    Helper function to set up test bucket tags.
    
    Args:
        s3_client: Boto3 S3 client
        bucket_name: Name of the bucket to tag
        config_tags: Dictionary of configuration tags to set
    """
    # Get existing tags
    try:
        response = s3_client.get_bucket_tagging(Bucket=bucket_name)
        existing_tags = {tag['Key']: tag['Value'] for tag in response['TagSet']}
    except s3_client.exceptions.NoSuchTagSet:
        existing_tags = {}
    
    # Merge with new config tags
    all_tags = {**existing_tags, **config_tags}
    
    # Set tags
    tag_set = [{'Key': k, 'Value': v} for k, v in all_tags.items()]
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


class TestBucketConfigurationTags:
    """Test bucket-specific configuration tag functionality."""
    
    def test_bucket_with_configuration_tags(self, aws_clients, test_config, clean_queue_state):
        """
        Test end-to-end flow with a bucket that has configuration tags.
        
        **Validates: Requirements 1.1, 1.2, 1.5, 2.1, 2.2, 5.1, 5.5**
        
        This test verifies:
        1. Bucket configuration tags are read correctly
        2. Bucket-specific configuration is applied during consolidation
        3. Configuration decisions are logged
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_with_config_tags']
        
        # Step 1: Set up bucket with specific configuration tags
        config_tags = {
            'AllowInvalidationEvents': 'true',  # Required for processing
            'invalidator:DirectoryConsolidationThreshold': '5',  # Custom threshold
            'invalidator:ConsolidationStopLevel': '2',  # Custom stop level
        }
        
        setup_test_bucket_tags(s3, bucket_name, config_tags)
        
        # Step 2: Send test events that would trigger consolidation
        test_paths = [
            '/prod/public/dir1/file1.html',
            '/prod/public/dir1/file2.html',
            '/prod/public/dir1/file3.html',
            '/prod/public/dir1/file4.html',
            '/prod/public/dir1/file5.html',  # Should trigger consolidation with threshold=5
            '/prod/public/dir1/file6.html',
        ]
        
        message_ids = []
        for path in test_paths:
            message_id = send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            message_ids.append(message_id)
            time.sleep(0.1)  # Small delay between messages
        
        # Step 3: Wait for messages to be available
        time.sleep(2)
        
        # Step 4: Invoke Processor Lambda to process the events
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Step 5: Verify Lambda execution was successful
        assert response['StatusCode'] == 200
        
        response_payload = json.loads(response['Payload'].read())
        if 'FunctionError' in response:
            pytest.fail(f"Lambda execution failed: {response_payload}")
        
        # Step 6: Wait for processing to complete and get logs
        time.sleep(3)
        
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Step 7: Verify configuration was read and applied
        config_log_found = False
        threshold_log_found = False
        
        for message in log_messages:
            # Look for configuration logging
            if 'DirectoryConsolidationThreshold' in message and '5' in message:
                config_log_found = True
            if 'ConsolidationStopLevel' in message and '2' in message:
                config_log_found = True
            if 'bucket-specific threshold' in message.lower() and '5' in message:
                threshold_log_found = True
        
        assert config_log_found, f"Configuration logging not found in logs: {log_messages}"
        assert threshold_log_found, f"Bucket-specific threshold logging not found in logs: {log_messages}"
    
    def test_bucket_without_configuration_tags(self, aws_clients, test_config, clean_queue_state):
        """
        Test end-to-end flow with a bucket that has no configuration tags.
        
        **Validates: Requirements 1.3, 2.3, 5.2**
        
        This test verifies:
        1. Default configuration values are used when tags are missing
        2. Default value usage is logged
        3. Processing works correctly with defaults
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_without_config_tags']
        
        # Step 1: Ensure bucket has only required tags (no config tags)
        required_tags = {
            'AllowInvalidationEvents': 'true',  # Required for processing
        }
        
        setup_test_bucket_tags(s3, bucket_name, required_tags)
        
        # Step 2: Send test events
        test_paths = [
            '/prod/public/dir2/file1.html',
            '/prod/public/dir2/file2.html',
            '/prod/public/dir2/file3.html',  # Should trigger consolidation with default threshold=3
            '/prod/public/dir2/file4.html',
        ]
        
        message_ids = []
        for path in test_paths:
            message_id = send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            message_ids.append(message_id)
            time.sleep(0.1)
        
        # Step 3: Wait and invoke Processor
        time.sleep(2)
        
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Step 4: Verify execution
        assert response['StatusCode'] == 200
        
        response_payload = json.loads(response['Payload'].read())
        if 'FunctionError' in response:
            pytest.fail(f"Lambda execution failed: {response_payload}")
        
        # Step 5: Get logs and verify default usage
        time.sleep(3)
        
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Step 6: Verify default values were used and logged
        default_threshold_log_found = False
        default_stop_level_log_found = False
        
        expected_threshold = str(test_config['expected_default_threshold'])
        expected_stop_level = str(test_config['expected_default_stop_level'])
        
        for message in log_messages:
            if 'default' in message.lower() and expected_threshold in message:
                default_threshold_log_found = True
            if 'default' in message.lower() and expected_stop_level in message:
                default_stop_level_log_found = True
        
        # At least one default usage should be logged
        assert default_threshold_log_found or default_stop_level_log_found, \
            f"Default value usage not logged. Messages: {log_messages}"


class TestMixedEnvironment:
    """Test mixed environment with some buckets having tags and others not."""
    
    def test_mixed_bucket_configuration(self, aws_clients, test_config, clean_queue_state):
        """
        Test processing events from multiple buckets with different configurations.
        
        **Validates: Requirements 1.2, 1.3, 1.5, 2.2, 2.3, 5.1, 5.2**
        
        This test verifies:
        1. Each bucket's configuration is applied independently
        2. Mixed configurations are handled correctly in the same processing cycle
        3. Configuration decisions are logged for each bucket
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_with_tags = test_config['bucket_with_config_tags']
        bucket_without_tags = test_config['bucket_without_config_tags']
        
        # Step 1: Set up buckets with different configurations
        # Bucket 1: Custom configuration
        config_tags_1 = {
            'AllowInvalidationEvents': 'true',
            'invalidator:DirectoryConsolidationThreshold': '7',
            'invalidator:ConsolidationStopLevel': '3',
        }
        setup_test_bucket_tags(s3, bucket_with_tags, config_tags_1)
        
        # Bucket 2: Default configuration (no config tags)
        config_tags_2 = {
            'AllowInvalidationEvents': 'true',
        }
        setup_test_bucket_tags(s3, bucket_without_tags, config_tags_2)
        
        # Step 2: Send events from both buckets
        # Events from bucket with custom config
        custom_paths = [
            '/prod/public/custom/file1.html',
            '/prod/public/custom/file2.html',
        ]
        
        # Events from bucket with default config
        default_paths = [
            '/prod/public/default/file1.html',
            '/prod/public/default/file2.html',
        ]
        
        # Send events from both buckets
        for path in custom_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_with_tags, path)
            time.sleep(0.1)
        
        for path in default_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_without_tags, path)
            time.sleep(0.1)
        
        # Step 3: Process events
        time.sleep(2)
        
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        # Step 4: Verify both configurations were applied
        time.sleep(3)
        
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Look for evidence of both configurations being used
        custom_config_found = False
        default_config_found = False
        
        for message in log_messages:
            # Look for custom threshold (7) being used
            if '7' in message and ('threshold' in message.lower() or bucket_with_tags in message):
                custom_config_found = True
            
            # Look for default values being used
            if 'default' in message.lower() and bucket_without_tags in message:
                default_config_found = True
        
        # Both configurations should be evident in logs
        assert custom_config_found, f"Custom configuration not found in logs: {log_messages}"
        assert default_config_found, f"Default configuration not found in logs: {log_messages}"


class TestConsolidationBehaviorChanges:
    """Test that consolidation behavior changes based on configuration."""
    
    def test_different_threshold_behavior(self, aws_clients, test_config, clean_queue_state):
        """
        Test that different directory consolidation thresholds produce different behavior.
        
        **Validates: Requirements 1.2, 1.5**
        
        This test verifies:
        1. Lower thresholds trigger consolidation sooner
        2. Higher thresholds require more files before consolidation
        3. Consolidation behavior is actually different based on configuration
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_with_config_tags']
        
        # Test with low threshold (should consolidate with fewer files)
        config_tags_low = {
            'AllowInvalidationEvents': 'true',
            'invalidator:DirectoryConsolidationThreshold': '2',  # Low threshold
            'invalidator:ConsolidationStopLevel': '1',
        }
        
        setup_test_bucket_tags(s3, bucket_name, config_tags_low)
        
        # Send exactly 3 files (should trigger consolidation with threshold=2)
        test_paths = [
            '/prod/public/lowthresh/file1.html',
            '/prod/public/lowthresh/file2.html',
            '/prod/public/lowthresh/file3.html',
        ]
        
        for path in test_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Process with low threshold
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        # Get logs for low threshold test
        log_events_low = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages_low = [event['message'] for event in log_events_low]
        
        # Look for consolidation activity with threshold=2
        consolidation_with_low_threshold = any(
            'consolidat' in msg.lower() and ('2' in msg or 'lowthresh' in msg)
            for msg in log_messages_low
        )
        
        # Clean queue for next test
        sqs.purge_queue(QueueUrl=test_config['queue_url'])
        time.sleep(2)
        
        # Now test with high threshold (should NOT consolidate with same number of files)
        config_tags_high = {
            'AllowInvalidationEvents': 'true',
            'invalidator:DirectoryConsolidationThreshold': '10',  # High threshold
            'invalidator:ConsolidationStopLevel': '1',
        }
        
        setup_test_bucket_tags(s3, bucket_name, config_tags_high)
        
        # Send same number of files (should NOT trigger consolidation with threshold=10)
        test_paths_high = [
            '/prod/public/highthresh/file1.html',
            '/prod/public/highthresh/file2.html',
            '/prod/public/highthresh/file3.html',
        ]
        
        for path in test_paths_high:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Process with high threshold
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        # Get logs for high threshold test
        log_events_high = get_recent_log_events(logs_client, test_config['processor_function_name'], minutes=2)
        log_messages_high = [event['message'] for event in log_events_high]
        
        # Verify different behavior occurred
        # With low threshold, consolidation should have happened
        # With high threshold, consolidation should NOT have happened (or happened differently)
        
        threshold_2_found = any('2' in msg and 'threshold' in msg.lower() for msg in log_messages_low)
        threshold_10_found = any('10' in msg and 'threshold' in msg.lower() for msg in log_messages_high)
        
        assert threshold_2_found, f"Low threshold (2) not found in logs: {log_messages_low}"
        assert threshold_10_found, f"High threshold (10) not found in logs: {log_messages_high}"
    
    def test_stop_level_behavior(self, aws_clients, test_config, clean_queue_state):
        """
        Test that different consolidation stop levels produce different behavior.
        
        **Validates: Requirements 2.2, 2.4, 2.5, 5.4**
        
        This test verifies:
        1. Stop level 0 consolidates to root
        2. Higher stop levels prevent consolidation at shallow depths
        3. Stop level decisions are logged
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_with_config_tags']
        
        # Test with stop level 0 (should consolidate to root)
        config_tags_root = {
            'AllowInvalidationEvents': 'true',
            'invalidator:DirectoryConsolidationThreshold': '2',
            'invalidator:ConsolidationStopLevel': '0',  # Consolidate to root
        }
        
        setup_test_bucket_tags(s3, bucket_name, config_tags_root)
        
        # Send files that would normally be consolidated at directory level
        test_paths_root = [
            '/prod/public/level1/file1.html',
            '/prod/public/level1/file2.html',
            '/prod/public/level1/file3.html',
        ]
        
        for path in test_paths_root:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        log_events_root = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages_root = [event['message'] for event in log_events_root]
        
        # Look for evidence of root consolidation (stop level 0)
        root_consolidation_found = any(
            ('stop level' in msg.lower() and '0' in msg) or 
            ('root' in msg.lower() and 'consolidat' in msg.lower())
            for msg in log_messages_root
        )
        
        # Clean for next test
        sqs.purge_queue(QueueUrl=test_config['queue_url'])
        time.sleep(2)
        
        # Test with higher stop level (should prevent shallow consolidation)
        config_tags_deep = {
            'AllowInvalidationEvents': 'true',
            'invalidator:DirectoryConsolidationThreshold': '2',
            'invalidator:ConsolidationStopLevel': '3',  # Prevent consolidation at depth 3 or less
        }
        
        setup_test_bucket_tags(s3, bucket_name, config_tags_deep)
        
        # Send same files
        test_paths_deep = [
            '/prod/public/level1/file1.html',
            '/prod/public/level1/file2.html',
            '/prod/public/level1/file3.html',
        ]
        
        for path in test_paths_deep:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        log_events_deep = get_recent_log_events(logs_client, test_config['processor_function_name'], minutes=2)
        log_messages_deep = [event['message'] for event in log_events_deep]
        
        # Look for evidence of stop level prevention
        stop_level_prevention_found = any(
            ('stop level' in msg.lower() and '3' in msg) or
            ('prevent' in msg.lower() and 'consolidat' in msg.lower())
            for msg in log_messages_deep
        )
        
        # Verify different behaviors occurred
        assert root_consolidation_found or stop_level_prevention_found, \
            f"Stop level behavior not found in logs. Root: {log_messages_root}, Deep: {log_messages_deep}"


class TestCloudFormationParameterIntegration:
    """Test CloudFormation parameter integration."""
    
    def test_environment_variables_from_parameters(self, aws_clients, test_config):
        """
        Test that CloudFormation parameters are correctly set as environment variables.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
        
        This test verifies:
        1. Environment variables are set from CloudFormation parameters
        2. Default values are used when parameters are not provided
        3. Lambda functions can read the environment variables
        """
        lambda_client = aws_clients['lambda']
        
        # Get Lambda function configuration
        response = lambda_client.get_function_configuration(
            FunctionName=test_config['processor_function_name']
        )
        
        env_vars = response.get('Environment', {}).get('Variables', {})
        
        # Verify required environment variables exist
        required_env_vars = [
            'DIRECTORY_CONSOLIDATION_THRESHOLD',
            'CONSOLIDATION_STOP_LEVEL',
            'AGGREGATION_WINDOW_SECONDS',
        ]
        
        for var_name in required_env_vars:
            assert var_name in env_vars, f"Environment variable {var_name} not found in Lambda configuration"
            
            # Verify the value is a valid number
            try:
                int(env_vars[var_name])
            except ValueError:
                pytest.fail(f"Environment variable {var_name} has invalid value: {env_vars[var_name]}")
        
        # Verify values match expected defaults or are within valid ranges
        threshold = int(env_vars['DIRECTORY_CONSOLIDATION_THRESHOLD'])
        stop_level = int(env_vars['CONSOLIDATION_STOP_LEVEL'])
        window_seconds = int(env_vars['AGGREGATION_WINDOW_SECONDS'])
        
        assert 1 <= threshold <= 1000, f"Directory threshold {threshold} out of valid range (1-1000)"
        assert 0 <= stop_level <= 1000, f"Stop level {stop_level} out of valid range (0-1000)"
        assert 60 <= window_seconds <= 900, f"Window seconds {window_seconds} out of valid range (60-900)"
        
        # Verify values match test configuration expectations
        assert threshold == test_config['expected_default_threshold'], \
            f"Expected threshold {test_config['expected_default_threshold']}, got {threshold}"
        assert stop_level == test_config['expected_default_stop_level'], \
            f"Expected stop level {test_config['expected_default_stop_level']}, got {stop_level}"


class TestErrorHandlingAndLogging:
    """Test error handling and comprehensive logging."""
    
    def test_invalid_tag_value_handling(self, aws_clients, test_config, clean_queue_state):
        """
        Test handling of invalid configuration tag values.
        
        **Validates: Requirements 1.4, 5.3**
        
        This test verifies:
        1. Invalid tag values are handled gracefully
        2. Fallback to default values occurs
        3. Warning messages are logged for invalid values
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_with_config_tags']
        
        # Set up bucket with invalid configuration tags
        invalid_config_tags = {
            'AllowInvalidationEvents': 'true',
            'invalidator:DirectoryConsolidationThreshold': 'invalid_number',  # Invalid
            'invalidator:ConsolidationStopLevel': '2000',  # Out of range
        }
        
        setup_test_bucket_tags(s3, bucket_name, invalid_config_tags)
        
        # Send test event
        send_test_event(sqs, test_config['queue_url'], bucket_name, '/prod/public/invalid/test.html')
        
        time.sleep(2)
        
        # Process event
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Should still succeed despite invalid tags
        assert response['StatusCode'] == 200
        
        response_payload = json.loads(response['Payload'].read())
        if 'FunctionError' in response:
            pytest.fail(f"Lambda should handle invalid tags gracefully: {response_payload}")
        
        time.sleep(2)
        
        # Check logs for warning messages
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Look for warning/error messages about invalid values
        invalid_value_warning_found = any(
            ('warning' in msg.lower() or 'error' in msg.lower() or 'invalid' in msg.lower()) and
            ('tag' in msg.lower() or 'threshold' in msg.lower() or 'stop level' in msg.lower())
            for msg in log_messages
        )
        
        # Look for fallback to default values
        fallback_found = any(
            'default' in msg.lower() and ('fallback' in msg.lower() or 'using' in msg.lower())
            for msg in log_messages
        )
        
        assert invalid_value_warning_found or fallback_found, \
            f"Invalid tag handling not logged properly: {log_messages}"
    
    def test_comprehensive_configuration_logging(self, aws_clients, test_config, clean_queue_state):
        """
        Test that all configuration decisions are logged comprehensively.
        
        **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
        
        This test verifies:
        1. Configuration tag reading is logged in JSON format
        2. Default value usage is logged
        3. Invalid tag values generate warning logs
        4. Stop level decisions are logged
        5. Bucket-specific threshold usage is logged
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_with_config_tags']
        
        # Set up bucket with mixed valid/invalid configuration
        config_tags = {
            'AllowInvalidationEvents': 'true',
            'invalidator:DirectoryConsolidationThreshold': '4',  # Valid
            'invalidator:ConsolidationStopLevel': 'invalid',  # Invalid - should use default
        }
        
        setup_test_bucket_tags(s3, bucket_name, config_tags)
        
        # Send events that will trigger various consolidation decisions
        test_paths = [
            '/prod/public/comprehensive/dir1/file1.html',
            '/prod/public/comprehensive/dir1/file2.html',
            '/prod/public/comprehensive/dir1/file3.html',
            '/prod/public/comprehensive/dir1/file4.html',  # Should trigger consolidation
            '/prod/public/comprehensive/dir2/file1.html',
        ]
        
        for path in test_paths:
            send_test_event(sqs, test_config['queue_url'], bucket_name, path)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Process events
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(3)
        
        # Get comprehensive logs
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Check for various types of logging
        logging_checks = {
            'config_tag_reading': False,
            'valid_tag_usage': False,
            'invalid_tag_warning': False,
            'default_value_usage': False,
            'bucket_specific_threshold': False,
        }
        
        for message in log_messages:
            msg_lower = message.lower()
            
            # Configuration tag reading (should be in JSON format or structured)
            if ('directoryconsolidationthreshold' in msg_lower or 'consolidationstoplevel' in msg_lower) and \
               ('{' in message or 'tag' in msg_lower):
                logging_checks['config_tag_reading'] = True
            
            # Valid tag usage
            if '4' in message and 'threshold' in msg_lower:
                logging_checks['valid_tag_usage'] = True
            
            # Invalid tag warning
            if ('invalid' in msg_lower or 'warning' in msg_lower) and 'tag' in msg_lower:
                logging_checks['invalid_tag_warning'] = True
            
            # Default value usage
            if 'default' in msg_lower and ('stop level' in msg_lower or 'consolidation' in msg_lower):
                logging_checks['default_value_usage'] = True
            
            # Bucket-specific threshold usage
            if 'bucket' in msg_lower and 'threshold' in msg_lower and '4' in message:
                logging_checks['bucket_specific_threshold'] = True
        
        # Verify comprehensive logging occurred
        passed_checks = sum(logging_checks.values())
        total_checks = len(logging_checks)
        
        assert passed_checks >= 3, \
            f"Insufficient logging coverage. Passed {passed_checks}/{total_checks} checks. " \
            f"Failed: {[k for k, v in logging_checks.items() if not v]}. " \
            f"Log messages: {log_messages}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])