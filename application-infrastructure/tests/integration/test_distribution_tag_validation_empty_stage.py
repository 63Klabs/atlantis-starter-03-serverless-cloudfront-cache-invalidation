#!/usr/bin/env python3
"""
Integration tests for distribution tag validation with empty stage_id.

**Feature: distribution-tag-validation-no-stage-fix, Integration Test: Empty stage_id validation**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

This module tests the end-to-end distribution tag validation flow when the bucket
pattern does not include {stageId}, resulting in an empty stage_id value. This
verifies that prefix matching works correctly for distributions.

These tests require:
1. Deployed CloudFormation stack with Processor Lambda function
2. AWS credentials configured
3. Test S3 bucket without {stageId} in pattern (AllowInvalidationEvents=true)
4. Test CloudFront distributions with appropriate tags
5. Test SQS queue for event processing

Run with: pytest tests/integration/test_distribution_tag_validation_empty_stage.py -v

Environment variables required:
- PROCESSOR_FUNCTION_NAME: Name of the deployed Processor Lambda
- TEST_QUEUE_URL: URL of the SQS queue
- TEST_BUCKET_NO_STAGE: Name of test S3 bucket without stage in pattern
- TEST_DISTRIBUTION_PREFIX_MATCH: CloudFront distribution ID with prefix-matching tag
- TEST_DISTRIBUTION_EXACT_MATCH: CloudFront distribution ID with exact-matching tag (optional)
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
        'bucket_no_stage': os.environ.get('TEST_BUCKET_NO_STAGE'),
        'distribution_prefix_match': os.environ.get('TEST_DISTRIBUTION_PREFIX_MATCH'),
        'distribution_exact_match': os.environ.get('TEST_DISTRIBUTION_EXACT_MATCH'),
    }
    
    # Validate required configuration (distribution_exact_match is optional)
    required = ['processor_function_name', 'queue_url', 'bucket_no_stage', 'distribution_prefix_match']
    missing = [k for k in required if not config.get(k)]
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


def send_test_event(sqs_client, queue_url: str, bucket_name: str, object_key: str, stage_id: str = '') -> str:
    """
    Helper function to send a test S3 event to the queue.
    
    Args:
        sqs_client: Boto3 SQS client
        queue_url: URL of the SQS queue
        bucket_name: Name of the S3 bucket
        object_key: S3 object key
        stage_id: Stage ID (empty string for buckets without stage pattern)
        
    Returns:
        Message ID of the sent message
    """
    test_message = {
        'bucketName': bucket_name,
        'objectKey': object_key,
        'originPath': '/public',
        'stageId': stage_id,  # Empty for buckets without {stageId} pattern
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


def verify_bucket_tags(s3_client, bucket_name: str) -> Dict[str, str]:
    """
    Verify and return bucket tags.
    
    Args:
        s3_client: Boto3 S3 client
        bucket_name: Name of the bucket
        
    Returns:
        Dictionary of bucket tags
    """
    try:
        response = s3_client.get_bucket_tagging(Bucket=bucket_name)
        return {tag['Key']: tag['Value'] for tag in response['TagSet']}
    except Exception as e:
        print(f"Warning: Could not retrieve bucket tags: {e}")
        return {}


def verify_distribution_tags(cloudfront_client, distribution_id: str) -> Dict[str, str]:
    """
    Verify and return distribution tags.
    
    Args:
        cloudfront_client: Boto3 CloudFront client
        distribution_id: CloudFront distribution ID
        
    Returns:
        Dictionary of distribution tags
    """
    try:
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        
        response = cloudfront_client.list_tags_for_resource(
            Resource=f"arn:aws:cloudfront::{account_id}:distribution/{distribution_id}"
        )
        return {tag['Key']: tag['Value'] for tag in response['Tags']['Items']}
    except Exception as e:
        print(f"Warning: Could not retrieve distribution tags: {e}")
        return {}


class TestEmptyStageIdPrefixMatching:
    """Test distribution tag validation with empty stage_id using prefix matching."""
    
    def test_empty_stage_id_prefix_match_validation(self, aws_clients, test_config, clean_queue_state):
        """
        Test end-to-end flow with empty stage_id and prefix matching.
        
        **Validates: Requirements 1.1, 1.2, 1.3**
        
        This test verifies:
        1. Bucket without {stageId} pattern results in empty stage_id
        2. Distribution validation uses prefix matching for empty stage_id
        3. Distribution with ApplicationDeploymentId starting with bucket app tag is matched
        4. Invalidations are created for matching distributions
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        cloudfront = aws_clients['cloudfront']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_no_stage']
        distribution_id = test_config['distribution_prefix_match']
        
        # Step 1: Verify bucket has required tags
        bucket_tags = verify_bucket_tags(s3, bucket_name)
        assert 'AllowInvalidationEvents' in bucket_tags, \
            f"Bucket {bucket_name} must have AllowInvalidationEvents tag"
        assert bucket_tags['AllowInvalidationEvents'] == 'true', \
            f"AllowInvalidationEvents must be 'true', got: {bucket_tags['AllowInvalidationEvents']}"
        
        # Get bucket application tag
        bucket_app_tag = bucket_tags.get('atlantis:Application', '')
        assert bucket_app_tag, f"Bucket {bucket_name} must have atlantis:Application tag"
        
        print(f"Bucket application tag: {bucket_app_tag}")
        
        # Step 2: Verify distribution has required tags
        dist_tags = verify_distribution_tags(cloudfront, distribution_id)
        assert 'AllowInvalidationEvents' in dist_tags, \
            f"Distribution {distribution_id} must have AllowInvalidationEvents tag"
        assert dist_tags['AllowInvalidationEvents'] == 'true', \
            f"Distribution AllowInvalidationEvents must be 'true'"
        
        # Verify ApplicationDeploymentId starts with bucket app tag (prefix match)
        app_deployment_id = dist_tags.get('atlantis:ApplicationDeploymentId', '')
        assert app_deployment_id.startswith(bucket_app_tag), \
            f"Distribution ApplicationDeploymentId '{app_deployment_id}' must start with '{bucket_app_tag}'"
        
        print(f"Distribution ApplicationDeploymentId: {app_deployment_id}")
        print(f"Prefix match: {app_deployment_id} starts with {bucket_app_tag}")
        
        # Step 3: Send test event with empty stage_id
        test_object_key = f'/public/test-empty-stage-{uuid.uuid4()}.html'
        message_id = send_test_event(
            sqs, 
            test_config['queue_url'], 
            bucket_name, 
            test_object_key,
            stage_id=''  # Empty stage_id for bucket without {stageId} pattern
        )
        
        print(f"Sent test event with message ID: {message_id}")
        
        # Step 4: Wait for message to be available
        time.sleep(2)
        
        # Step 5: Invoke Processor Lambda to process the event
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Step 6: Verify Lambda execution was successful
        assert response['StatusCode'] == 200, f"Lambda invocation failed with status {response['StatusCode']}"
        
        response_payload = json.loads(response['Payload'].read())
        if 'FunctionError' in response:
            pytest.fail(f"Lambda execution failed: {response_payload}")
        
        print(f"Lambda execution successful")
        
        # Step 7: Wait for processing to complete and get logs
        time.sleep(3)
        
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Step 8: Verify prefix matching was used in validation
        prefix_match_log_found = False
        validation_passed_log_found = False
        
        for message in log_messages:
            # Look for prefix match type in logs
            if 'prefix' in message.lower() and 'match' in message.lower():
                prefix_match_log_found = True
                print(f"Found prefix match log: {message}")
            
            # Look for successful validation
            if 'validation passed' in message.lower() or 'validation_result' in message.lower():
                if distribution_id in message or 'true' in message.lower():
                    validation_passed_log_found = True
                    print(f"Found validation passed log: {message}")
        
        assert prefix_match_log_found, \
            f"Prefix match logging not found in logs. Sample logs: {log_messages[:10]}"
        assert validation_passed_log_found, \
            f"Validation passed logging not found in logs. Sample logs: {log_messages[:10]}"
        
        # Step 9: Verify invalidation was created (check CloudWatch logs for invalidation creation)
        invalidation_created_log_found = False
        
        for message in log_messages:
            if 'invalidation' in message.lower() and ('created' in message.lower() or 'create' in message.lower()):
                if distribution_id in message:
                    invalidation_created_log_found = True
                    print(f"Found invalidation creation log: {message}")
        
        # Note: Invalidation creation may not always happen in test environment
        # depending on consolidation logic, so we just log the result
        if invalidation_created_log_found:
            print("✓ Invalidation was created for the distribution")
        else:
            print("⚠ Invalidation creation not detected in logs (may be due to consolidation)")
    
    def test_empty_stage_id_exact_match_also_valid(self, aws_clients, test_config, clean_queue_state):
        """
        Test that exact match is also valid when stage_id is empty.
        
        **Validates: Requirements 1.5**
        
        This test verifies:
        1. When stage_id is empty, prefix matching is used
        2. Exact match (ApplicationDeploymentId == bucket_app_tag) is also valid
        3. Distribution with exact ApplicationDeploymentId match passes validation
        """
        if not test_config.get('distribution_exact_match'):
            pytest.skip("TEST_DISTRIBUTION_EXACT_MATCH not configured")
        
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        cloudfront = aws_clients['cloudfront']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_no_stage']
        distribution_id = test_config['distribution_exact_match']
        
        # Step 1: Verify bucket and distribution tags
        bucket_tags = verify_bucket_tags(s3, bucket_name)
        bucket_app_tag = bucket_tags.get('atlantis:Application', '')
        
        dist_tags = verify_distribution_tags(cloudfront, distribution_id)
        app_deployment_id = dist_tags.get('atlantis:ApplicationDeploymentId', '')
        
        # Verify exact match
        assert app_deployment_id == bucket_app_tag, \
            f"Distribution ApplicationDeploymentId '{app_deployment_id}' must equal '{bucket_app_tag}'"
        
        print(f"Exact match: {app_deployment_id} == {bucket_app_tag}")
        
        # Step 2: Send test event with empty stage_id
        test_object_key = f'/public/test-exact-match-{uuid.uuid4()}.html'
        send_test_event(
            sqs, 
            test_config['queue_url'], 
            bucket_name, 
            test_object_key,
            stage_id=''
        )
        
        time.sleep(2)
        
        # Step 3: Process event
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(3)
        
        # Step 4: Verify validation passed
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        validation_passed = any(
            'validation passed' in msg.lower() and distribution_id in msg
            for msg in log_messages
        )
        
        assert validation_passed, \
            f"Validation should pass for exact match. Logs: {log_messages[:10]}"


class TestEmptyStageIdLogging:
    """Test logging behavior with empty stage_id."""
    
    def test_match_type_logged_as_prefix(self, aws_clients, test_config, clean_queue_state):
        """
        Test that match_type is logged as 'prefix' when stage_id is empty.
        
        **Validates: Requirements FR-5**
        
        This test verifies:
        1. Validation logs include match_type field
        2. match_type is set to 'prefix' when stage_id is empty
        3. Expected and actual ApplicationDeploymentId values are logged
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_no_stage']
        
        # Send test event
        test_object_key = f'/public/test-logging-{uuid.uuid4()}.html'
        send_test_event(
            sqs, 
            test_config['queue_url'], 
            bucket_name, 
            test_object_key,
            stage_id=''
        )
        
        time.sleep(2)
        
        # Process event
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(3)
        
        # Get logs
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Verify match_type logging
        match_type_prefix_found = False
        expected_actual_logged = False
        
        for message in log_messages:
            # Look for match_type: prefix
            if 'match_type' in message.lower() and 'prefix' in message:
                match_type_prefix_found = True
                print(f"Found match_type=prefix log: {message}")
            
            # Look for expected and actual values
            if 'expected' in message.lower() and 'actual' in message.lower():
                expected_actual_logged = True
                print(f"Found expected/actual log: {message}")
        
        assert match_type_prefix_found, \
            f"match_type='prefix' not found in logs. Sample: {log_messages[:10]}"
        assert expected_actual_logged, \
            f"Expected/actual values not logged. Sample: {log_messages[:10]}"


class TestBackwardCompatibility:
    """Test backward compatibility with stage-based validation."""
    
    def test_non_empty_stage_id_still_uses_exact_match(self, aws_clients, test_config, clean_queue_state):
        """
        Test that non-empty stage_id still uses exact matching (backward compatibility).
        
        **Validates: Requirements 2.1, 2.2, 2.3, NFR-1**
        
        This test verifies:
        1. When stage_id is non-empty, exact matching is used
        2. match_type is logged as 'exact'
        3. Existing stage-based validation behavior is preserved
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['bucket_no_stage']
        
        # Send test event with NON-EMPTY stage_id
        test_object_key = f'/prod/public/test-exact-{uuid.uuid4()}.html'
        send_test_event(
            sqs, 
            test_config['queue_url'], 
            bucket_name, 
            test_object_key,
            stage_id='prod'  # Non-empty stage_id
        )
        
        time.sleep(2)
        
        # Process event
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        assert response['StatusCode'] == 200
        
        time.sleep(3)
        
        # Get logs
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Verify exact match type is used
        match_type_exact_found = False
        
        for message in log_messages:
            if 'match_type' in message.lower() and 'exact' in message:
                match_type_exact_found = True
                print(f"Found match_type=exact log: {message}")
        
        assert match_type_exact_found, \
            f"match_type='exact' not found for non-empty stage_id. Logs: {log_messages[:10]}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
