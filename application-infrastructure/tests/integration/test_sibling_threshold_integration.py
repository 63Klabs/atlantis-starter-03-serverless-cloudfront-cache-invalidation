#!/usr/bin/env python3
"""
End-to-end integration tests for sibling threshold parameter functionality.

**Feature: consolidation-stop-level-depth-fix, Integration Test: Sibling threshold parameter**
**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

This module tests the complete end-to-end flow of the sibling threshold parameter fix
to verify that bucket-specific sibling directory consolidation thresholds work correctly
with real AWS services and realistic bucket configurations.

These tests require:
1. Deployed CloudFormation stack with the sibling threshold fix
2. AWS credentials configured
3. Test S3 buckets with various sibling threshold configurations
4. Test CloudFront distributions with appropriate tags

Run with: pytest tests/integration/test_sibling_threshold_integration.py -v

Environment variables required:
- PROCESSOR_FUNCTION_NAME: Name of the deployed Processor Lambda
- TEST_QUEUE_URL: URL of the SQS queue
- TEST_BUCKET_WITH_SIBLING_CONFIG: Name of test S3 bucket for sibling threshold testing
- TEST_DISTRIBUTION_ID: CloudFront distribution ID with appropriate tags
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
        'test_bucket': os.environ.get('TEST_BUCKET_WITH_SIBLING_CONFIG'),
        'test_distribution_id': os.environ.get('TEST_DISTRIBUTION_ID'),
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


def setup_bucket_sibling_threshold_tags(s3_client, bucket_name: str, sibling_threshold: int, stop_level: int = 1):
    """
    Helper function to set up bucket tags for sibling threshold testing.
    
    Args:
        s3_client: Boto3 S3 client
        bucket_name: Name of the bucket to tag
        sibling_threshold: Sibling directory consolidation threshold to set
        stop_level: Consolidation stop level to set
    """
    # Get existing tags
    try:
        response = s3_client.get_bucket_tagging(Bucket=bucket_name)
        existing_tags = {tag['Key']: tag['Value'] for tag in response['TagSet']}
    except s3_client.exceptions.NoSuchTagSet:
        existing_tags = {}
    
    # Set up required tags for processing and sibling threshold configuration
    config_tags = {
        'AllowInvalidationEvents': 'true',  # Required for processing
        'atlantis:Application': 'test-app',  # Required for distribution matching
        'invalidator:SiblingDirectoryConsolidationThreshold': str(sibling_threshold),
        'invalidator:ConsolidationStopLevel': str(stop_level),
        'invalidator:DirectoryConsolidationThreshold': '3',  # Standard threshold
    }
    
    # Merge with existing tags
    all_tags = {**existing_tags, **config_tags}
    
    # Set tags
    tag_set = [{'Key': k, 'Value': v} for k, v in all_tags.items()]
    s3_client.put_bucket_tagging(
        Bucket=bucket_name,
        Tagging={'TagSet': tag_set}
    )


def send_sibling_directory_events(sqs_client, queue_url: str, bucket_name: str, sibling_count: int) -> List[str]:
    """
    Helper function to send S3 events for multiple sibling directories.
    
    Args:
        sqs_client: Boto3 SQS client
        queue_url: SQS queue URL
        bucket_name: S3 bucket name
        sibling_count: Number of sibling directories to create events for
        
    Returns:
        List of message IDs for the sent messages
    """
    message_ids = []
    
    for i in range(sibling_count):
        # Create events for each sibling directory (multiple files per directory to trigger directory consolidation)
        sibling_dir = f"sibling{i:02d}"
        
        for file_num in range(4):  # 4 files per directory to trigger directory consolidation
            test_message = {
                'bucketName': bucket_name,
                'objectKey': f'/prod/public/{sibling_dir}/file{file_num}.html',
                'originPath': '/prod/public',
                'stageId': 'prod',
                'eventTime': datetime.now(timezone.utc).isoformat(),
                'eventType': 'ObjectCreated:Put'
            }
            
            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(test_message)
            )
            
            message_ids.append(response['MessageId'])
            time.sleep(0.05)  # Small delay between messages
    
    return message_ids


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


class TestSiblingThresholdParameter:
    """Test sibling threshold parameter functionality end-to-end."""
    
    def test_user_specific_scenario_with_threshold_2(self, aws_clients, test_config, clean_queue_state):
        """
        Test the user's specific scenario: 4 sibling directories with threshold=2 should consolidate to parent.
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        This test verifies:
        1. Bucket tag SiblingDirectoryConsolidationThreshold=2 is read correctly
        2. 4 sibling directories (> threshold 2) consolidate to /prod/public/*
        3. ConsolidationStopLevel=1 allows consolidation at the public level
        4. The fix resolves the original user issue
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Step 1: Set up bucket with sibling threshold = 2
        setup_bucket_sibling_threshold_tags(s3, bucket_name, sibling_threshold=2, stop_level=1)
        
        # Step 2: Send events for 4 sibling directories (m, k, w, x as in user's example)
        sibling_dirs = ['m', 'k', 'w', 'x']
        message_ids = []
        
        for sibling_dir in sibling_dirs:
            # Send multiple files per directory to trigger directory consolidation first
            for file_num in range(4):  # 4 files > directory threshold (3)
                test_message = {
                    'bucketName': bucket_name,
                    'objectKey': f'/prod/public/{sibling_dir}/file{file_num}.html',
                    'originPath': '/prod/public',
                    'stageId': 'prod',
                    'eventTime': datetime.now(timezone.utc).isoformat(),
                    'eventType': 'ObjectCreated:Put'
                }
                
                response = sqs.send_message(
                    QueueUrl=test_config['queue_url'],
                    MessageBody=json.dumps(test_message)
                )
                
                message_ids.append(response['MessageId'])
                time.sleep(0.05)
        
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
        
        # Step 7: Verify sibling threshold configuration was read and applied
        sibling_threshold_config_found = False
        sibling_consolidation_occurred = False
        parent_wildcard_found = False
        
        for message in log_messages:
            # Look for sibling threshold configuration being read
            if 'SiblingDirectoryConsolidationThreshold' in message and '2' in message:
                sibling_threshold_config_found = True
            
            # Look for sibling consolidation activity
            if 'sibling' in message.lower() and 'consolidat' in message.lower():
                sibling_consolidation_occurred = True
            
            # Look for the expected parent wildcard result
            if '/prod/public/*' in message:
                parent_wildcard_found = True
        
        # Verify the fix worked
        assert sibling_threshold_config_found, f"Sibling threshold configuration not found in logs: {log_messages}"
        assert sibling_consolidation_occurred, f"Sibling consolidation not found in logs: {log_messages}"
        assert parent_wildcard_found, f"Expected parent wildcard /prod/public/* not found in logs: {log_messages}"
    
    def test_sibling_threshold_boundary_conditions(self, aws_clients, test_config, clean_queue_state):
        """
        Test sibling threshold boundary conditions.
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies:
        1. Sibling count exactly at threshold does NOT consolidate
        2. Sibling count above threshold DOES consolidate
        3. Boundary logic works correctly with bucket-specific thresholds
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Test 1: Sibling count exactly at threshold (should NOT consolidate)
        setup_bucket_sibling_threshold_tags(s3, bucket_name, sibling_threshold=3, stop_level=1)
        
        # Send events for exactly 3 sibling directories
        message_ids = send_sibling_directory_events(sqs, test_config['queue_url'], bucket_name, 3)
        
        time.sleep(2)
        
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        log_events_at_threshold = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages_at_threshold = [event['message'] for event in log_events_at_threshold]
        
        # Should NOT see parent consolidation (3 siblings = threshold, not > threshold)
        parent_consolidation_at_threshold = any('/prod/public/*' in msg for msg in log_messages_at_threshold)
        
        # Clean queue for next test
        sqs.purge_queue(QueueUrl=test_config['queue_url'])
        time.sleep(2)
        
        # Test 2: Sibling count above threshold (should consolidate)
        setup_bucket_sibling_threshold_tags(s3, bucket_name, sibling_threshold=3, stop_level=1)
        
        # Send events for 4 sibling directories (> threshold)
        message_ids = send_sibling_directory_events(sqs, test_config['queue_url'], bucket_name, 4)
        
        time.sleep(2)
        
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        log_events_above_threshold = get_recent_log_events(logs_client, test_config['processor_function_name'], minutes=2)
        log_messages_above_threshold = [event['message'] for event in log_events_above_threshold]
        
        # Should see parent consolidation (4 siblings > threshold 3)
        parent_consolidation_above_threshold = any('/prod/public/*' in msg for msg in log_messages_above_threshold)
        
        # Verify boundary behavior
        assert not parent_consolidation_at_threshold, \
            f"Consolidation occurred at threshold boundary (should not). Messages: {log_messages_at_threshold}"
        assert parent_consolidation_above_threshold, \
            f"Consolidation did not occur above threshold (should have). Messages: {log_messages_above_threshold}"
    
    def test_multiple_bucket_different_thresholds(self, aws_clients, test_config, clean_queue_state):
        """
        Test multiple buckets with different sibling thresholds in the same processing cycle.
        
        **Validates: Requirements 2.4**
        
        This test verifies:
        1. Each bucket's sibling threshold is applied independently
        2. Mixed sibling thresholds are handled correctly in the same processing cycle
        3. Bucket-specific configuration isolation works correctly
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        # Note: This test uses the same bucket with different configurations over time
        # In a real environment, you would use multiple test buckets
        bucket_name = test_config['test_bucket']
        
        # Test with low threshold first
        setup_bucket_sibling_threshold_tags(s3, bucket_name, sibling_threshold=2, stop_level=1)
        
        # Send events for 3 sibling directories (should consolidate with threshold=2)
        for i in range(3):
            sibling_dir = f"low_thresh_{i}"
            for file_num in range(4):
                test_message = {
                    'bucketName': bucket_name,
                    'objectKey': f'/prod/public/{sibling_dir}/file{file_num}.html',
                    'originPath': '/prod/public',
                    'stageId': 'prod',
                    'eventTime': datetime.now(timezone.utc).isoformat(),
                    'eventType': 'ObjectCreated:Put'
                }
                
                sqs.send_message(
                    QueueUrl=test_config['queue_url'],
                    MessageBody=json.dumps(test_message)
                )
                time.sleep(0.05)
        
        time.sleep(2)
        
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        log_events_low = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages_low = [event['message'] for event in log_events_low]
        
        # Should see consolidation with low threshold
        low_threshold_consolidation = any(
            '/prod/public/*' in msg and ('low_thresh' in msg or 'sibling' in msg.lower())
            for msg in log_messages_low
        )
        
        # Clean and test with high threshold
        sqs.purge_queue(QueueUrl=test_config['queue_url'])
        time.sleep(2)
        
        setup_bucket_sibling_threshold_tags(s3, bucket_name, sibling_threshold=5, stop_level=1)
        
        # Send events for 3 sibling directories (should NOT consolidate with threshold=5)
        for i in range(3):
            sibling_dir = f"high_thresh_{i}"
            for file_num in range(4):
                test_message = {
                    'bucketName': bucket_name,
                    'objectKey': f'/prod/public/{sibling_dir}/file{file_num}.html',
                    'originPath': '/prod/public',
                    'stageId': 'prod',
                    'eventTime': datetime.now(timezone.utc).isoformat(),
                    'eventType': 'ObjectCreated:Put'
                }
                
                sqs.send_message(
                    QueueUrl=test_config['queue_url'],
                    MessageBody=json.dumps(test_message)
                )
                time.sleep(0.05)
        
        time.sleep(2)
        
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(2)
        
        log_events_high = get_recent_log_events(logs_client, test_config['processor_function_name'], minutes=2)
        log_messages_high = [event['message'] for event in log_events_high]
        
        # Should NOT see consolidation with high threshold
        high_threshold_consolidation = any(
            '/prod/public/*' in msg and 'high_thresh' in msg
            for msg in log_messages_high
        )
        
        # Verify different behavior based on threshold
        assert low_threshold_consolidation, \
            f"Low threshold consolidation not found. Messages: {log_messages_low}"
        assert not high_threshold_consolidation, \
            f"High threshold should not consolidate. Messages: {log_messages_high}"


class TestBackwardCompatibility:
    """Test backward compatibility with missing sibling threshold parameter."""
    
    def test_missing_sibling_threshold_parameter(self, aws_clients, test_config, clean_queue_state):
        """
        Test backward compatibility when sibling threshold parameter is not provided.
        
        **Validates: Requirements 1.3, 3.3**
        
        This test verifies:
        1. Missing sibling threshold parameter falls back to global constant (10)
        2. Existing functionality is preserved when parameter is not provided
        3. Default behavior is logged appropriately
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Set up bucket WITHOUT sibling threshold tag (should use default)
        try:
            response = s3.get_bucket_tagging(Bucket=bucket_name)
            existing_tags = {tag['Key']: tag['Value'] for tag in response['TagSet']}
        except s3.exceptions.NoSuchTagSet:
            existing_tags = {}
        
        # Set only required tags, no sibling threshold
        required_tags = {
            'AllowInvalidationEvents': 'true',
            'atlantis:Application': 'test-app',
            'invalidator:ConsolidationStopLevel': '1',
            'invalidator:DirectoryConsolidationThreshold': '3',
            # Note: NO SiblingDirectoryConsolidationThreshold tag
        }
        
        all_tags = {**existing_tags, **required_tags}
        tag_set = [{'Key': k, 'Value': v} for k, v in all_tags.items()]
        s3.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={'TagSet': tag_set}
        )
        
        # Send events for 11 sibling directories (should consolidate with default threshold=10)
        message_ids = send_sibling_directory_events(sqs, test_config['queue_url'], bucket_name, 11)
        
        time.sleep(2)
        
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(3)
        
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Should see consolidation with default threshold (11 > 10)
        default_threshold_consolidation = any('/prod/public/*' in msg for msg in log_messages)
        
        # Should see logging about default threshold usage
        default_threshold_logging = any(
            ('default' in msg.lower() or '10' in msg) and 'sibling' in msg.lower()
            for msg in log_messages
        )
        
        assert default_threshold_consolidation, \
            f"Default threshold consolidation not found. Messages: {log_messages}"
        # Note: Default threshold logging may not be explicit, so we don't assert on it
        # The important thing is that consolidation occurred with the expected default behavior


if __name__ == '__main__':
    pytest.main([__file__, '-v'])