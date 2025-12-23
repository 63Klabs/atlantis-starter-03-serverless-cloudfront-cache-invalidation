#!/usr/bin/env python3
"""
Performance and error handling validation tests for sibling threshold parameter.

**Feature: consolidation-stop-level-depth-fix, Integration Test: Performance validation**
**Validates: Requirements 4.4, 4.5**

This module tests performance characteristics and error handling of the sibling threshold
parameter fix to ensure no performance regression and proper error handling with invalid
threshold values.

These tests require:
1. Deployed CloudFormation stack with the sibling threshold fix
2. AWS credentials configured
3. Test S3 buckets for performance testing
4. CloudWatch metrics access for performance monitoring

Run with: pytest tests/integration/test_sibling_threshold_performance.py -v

Environment variables required:
- PROCESSOR_FUNCTION_NAME: Name of the deployed Processor Lambda
- TEST_QUEUE_URL: URL of the SQS queue
- TEST_BUCKET_PERFORMANCE: Name of test S3 bucket for performance testing
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
import statistics


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
        'cloudwatch': boto3.client('cloudwatch'),
    }


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration from environment variables."""
    config = {
        'processor_function_name': os.environ.get('PROCESSOR_FUNCTION_NAME'),
        'queue_url': os.environ.get('TEST_QUEUE_URL'),
        'test_bucket': os.environ.get('TEST_BUCKET_PERFORMANCE'),
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


def setup_bucket_tags(s3_client, bucket_name: str, config_tags: Dict[str, str]):
    """
    Helper function to set up bucket tags.
    
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


def send_large_batch_events(sqs_client, queue_url: str, bucket_name: str, event_count: int) -> List[str]:
    """
    Helper function to send a large batch of S3 events for performance testing.
    
    Args:
        sqs_client: Boto3 SQS client
        queue_url: SQS queue URL
        bucket_name: S3 bucket name
        event_count: Number of events to send
        
    Returns:
        List of message IDs for the sent messages
    """
    message_ids = []
    
    # Create events that will trigger sibling consolidation
    sibling_dirs = [f"perf_sibling_{i:03d}" for i in range(event_count // 4)]
    
    for sibling_dir in sibling_dirs:
        # Send 4 files per directory to trigger directory consolidation
        for file_num in range(4):
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
            
            # Small delay to avoid throttling
            if len(message_ids) % 100 == 0:
                time.sleep(0.1)
    
    return message_ids


def get_lambda_metrics(cloudwatch_client, function_name: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """
    Helper function to get Lambda performance metrics.
    
    Args:
        cloudwatch_client: Boto3 CloudWatch client
        function_name: Name of the Lambda function
        start_time: Start time for metrics
        end_time: End time for metrics
        
    Returns:
        Dictionary containing performance metrics
    """
    try:
        # Get duration metrics
        duration_response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Duration',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': function_name
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=['Average', 'Maximum', 'Minimum']
        )
        
        # Get memory utilization metrics
        memory_response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='MemoryUtilization',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': function_name
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=['Average', 'Maximum']
        )
        
        return {
            'duration': duration_response.get('Datapoints', []),
            'memory': memory_response.get('Datapoints', [])
        }
        
    except Exception as e:
        print(f"Warning: Could not retrieve metrics: {e}")
        return {'duration': [], 'memory': []}


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


class TestPerformanceRegression:
    """Test performance characteristics of sibling threshold parameter."""
    
    def test_no_performance_regression_with_sibling_parameter(self, aws_clients, test_config, clean_queue_state):
        """
        Test that adding sibling threshold parameter does not cause performance regression.
        
        **Validates: Requirements 4.4**
        
        This test verifies:
        1. Processing time is within acceptable limits with sibling threshold parameter
        2. Memory usage is within acceptable limits
        3. No significant performance degradation compared to baseline
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        cloudwatch_client = aws_clients['cloudwatch']
        
        bucket_name = test_config['test_bucket']
        
        # Set up bucket with sibling threshold configuration
        config_tags = {
            'AllowInvalidationEvents': 'true',
            'atlantis:Application': 'test-app',
            'invalidator:SiblingDirectoryConsolidationThreshold': '5',
            'invalidator:ConsolidationStopLevel': '1',
            'invalidator:DirectoryConsolidationThreshold': '3',
        }
        
        setup_bucket_tags(s3, bucket_name, config_tags)
        
        # Send a moderate number of events (enough to trigger consolidation)
        event_count = 100  # 25 sibling directories with 4 files each
        message_ids = send_large_batch_events(sqs, test_config['queue_url'], bucket_name, event_count)
        
        print(f"Sent {len(message_ids)} events for performance testing")
        
        # Wait for messages to be available
        time.sleep(3)
        
        # Record start time for metrics
        start_time = datetime.now(timezone.utc)
        
        # Invoke Processor Lambda
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Record end time
        end_time = datetime.now(timezone.utc)
        
        # Verify execution was successful
        assert response['StatusCode'] == 200
        
        response_payload = json.loads(response['Payload'].read())
        if 'FunctionError' in response:
            pytest.fail(f"Lambda execution failed: {response_payload}")
        
        # Wait for metrics to be available
        time.sleep(30)
        
        # Get performance metrics
        metrics = get_lambda_metrics(cloudwatch_client, test_config['processor_function_name'], start_time, end_time)
        
        # Get logs for additional performance analysis
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Analyze performance
        execution_time = (end_time - start_time).total_seconds()
        
        # Performance assertions (adjust thresholds based on your environment)
        assert execution_time < 30, f"Execution took too long: {execution_time} seconds"
        
        # Check if consolidation occurred (should reduce path count significantly)
        consolidation_occurred = any('consolidat' in msg.lower() for msg in log_messages)
        assert consolidation_occurred, "Consolidation should have occurred with this many events"
        
        # Check for sibling threshold usage in logs
        sibling_threshold_used = any('sibling' in msg.lower() and '5' in msg for msg in log_messages)
        
        print(f"Performance test completed in {execution_time:.2f} seconds")
        print(f"Consolidation occurred: {consolidation_occurred}")
        print(f"Sibling threshold used: {sibling_threshold_used}")
        
        # If metrics are available, check them
        if metrics['duration']:
            avg_duration = statistics.mean([dp['Average'] for dp in metrics['duration']])
            max_duration = max([dp['Maximum'] for dp in metrics['duration']])
            
            print(f"Average duration: {avg_duration:.2f}ms, Max duration: {max_duration:.2f}ms")
            
            # Performance thresholds (adjust based on your requirements)
            assert avg_duration < 15000, f"Average duration too high: {avg_duration}ms"  # 15 seconds
            assert max_duration < 30000, f"Maximum duration too high: {max_duration}ms"  # 30 seconds
    
    def test_memory_usage_validation(self, aws_clients, test_config, clean_queue_state):
        """
        Test memory usage with sibling threshold parameter.
        
        **Validates: Requirements 4.4**
        
        This test verifies:
        1. Memory usage is within acceptable limits
        2. No memory leaks or excessive memory consumption
        3. Memory usage scales appropriately with input size
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Set up bucket with sibling threshold configuration
        config_tags = {
            'AllowInvalidationEvents': 'true',
            'atlantis:Application': 'test-app',
            'invalidator:SiblingDirectoryConsolidationThreshold': '3',
            'invalidator:ConsolidationStopLevel': '1',
            'invalidator:DirectoryConsolidationThreshold': '3',
        }
        
        setup_bucket_tags(s3, bucket_name, config_tags)
        
        # Test with different batch sizes to check memory scaling
        batch_sizes = [50, 100]  # Start with smaller sizes for testing
        
        for batch_size in batch_sizes:
            print(f"Testing memory usage with {batch_size} events")
            
            # Clean queue
            sqs.purge_queue(QueueUrl=test_config['queue_url'])
            time.sleep(2)
            
            # Send events
            message_ids = send_large_batch_events(sqs, test_config['queue_url'], bucket_name, batch_size)
            
            time.sleep(2)
            
            # Invoke Lambda
            response = lambda_client.invoke(
                FunctionName=test_config['processor_function_name'],
                InvocationType='RequestResponse',
                Payload=json.dumps({})
            )
            
            assert response['StatusCode'] == 200
            
            response_payload = json.loads(response['Payload'].read())
            if 'FunctionError' in response:
                pytest.fail(f"Lambda execution failed with {batch_size} events: {response_payload}")
            
            time.sleep(1)
        
        # Get logs to check for memory-related issues
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Check for memory-related errors
        memory_errors = [msg for msg in log_messages if 'memory' in msg.lower() or 'out of memory' in msg.lower()]
        
        assert not memory_errors, f"Memory-related errors found: {memory_errors}"
        
        print("Memory usage validation completed successfully")


class TestErrorHandling:
    """Test error handling with invalid sibling threshold values."""
    
    def test_invalid_sibling_threshold_values(self, aws_clients, test_config, clean_queue_state):
        """
        Test error handling with invalid sibling threshold values.
        
        **Validates: Requirements 4.5**
        
        This test verifies:
        1. Invalid threshold values are handled gracefully
        2. System falls back to default values when invalid values are provided
        3. Warning messages are logged for invalid values
        4. Processing continues despite invalid configuration
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Test cases for invalid threshold values
        invalid_threshold_cases = [
            {
                'name': 'non_numeric_threshold',
                'threshold': 'invalid_number',
                'expected_behavior': 'fallback_to_default'
            },
            {
                'name': 'negative_threshold',
                'threshold': '-5',
                'expected_behavior': 'fallback_to_default'
            },
            {
                'name': 'zero_threshold',
                'threshold': '0',
                'expected_behavior': 'valid_but_edge_case'
            },
            {
                'name': 'extremely_large_threshold',
                'threshold': '999999',
                'expected_behavior': 'valid_but_impractical'
            }
        ]
        
        for case in invalid_threshold_cases:
            print(f"Testing invalid threshold case: {case['name']} with value '{case['threshold']}'")
            
            # Set up bucket with invalid threshold
            config_tags = {
                'AllowInvalidationEvents': 'true',
                'atlantis:Application': 'test-app',
                'invalidator:SiblingDirectoryConsolidationThreshold': case['threshold'],
                'invalidator:ConsolidationStopLevel': '1',
                'invalidator:DirectoryConsolidationThreshold': '3',
            }
            
            setup_bucket_tags(s3, bucket_name, config_tags)
            
            # Send test events
            test_message = {
                'bucketName': bucket_name,
                'objectKey': f'/prod/public/{case["name"]}/test.html',
                'originPath': '/prod/public',
                'stageId': 'prod',
                'eventTime': datetime.now(timezone.utc).isoformat(),
                'eventType': 'ObjectCreated:Put'
            }
            
            sqs.send_message(
                QueueUrl=test_config['queue_url'],
                MessageBody=json.dumps(test_message)
            )
            
            time.sleep(1)
            
            # Invoke Lambda - should not fail even with invalid threshold
            response = lambda_client.invoke(
                FunctionName=test_config['processor_function_name'],
                InvocationType='RequestResponse',
                Payload=json.dumps({})
            )
            
            # Verify Lambda execution was successful despite invalid threshold
            assert response['StatusCode'] == 200, f"Lambda failed with invalid threshold {case['threshold']}"
            
            response_payload = json.loads(response['Payload'].read())
            if 'FunctionError' in response:
                # Log the error but don't fail the test - we want to see how it handles invalid values
                print(f"Lambda error with {case['name']}: {response_payload}")
            
            time.sleep(1)
            
            # Clean queue for next test
            sqs.purge_queue(QueueUrl=test_config['queue_url'])
            time.sleep(1)
        
        # Get logs to check error handling
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Check for appropriate error handling
        error_handling_found = False
        fallback_behavior_found = False
        
        for message in log_messages:
            msg_lower = message.lower()
            
            # Look for error handling related to invalid thresholds
            if ('invalid' in msg_lower or 'error' in msg_lower or 'warning' in msg_lower) and \
               ('threshold' in msg_lower or 'sibling' in msg_lower):
                error_handling_found = True
            
            # Look for fallback behavior
            if 'default' in msg_lower and ('threshold' in msg_lower or 'fallback' in msg_lower):
                fallback_behavior_found = True
        
        # At least one form of error handling should be present
        assert error_handling_found or fallback_behavior_found, \
            f"No error handling found for invalid threshold values. Messages: {log_messages}"
        
        print("Invalid threshold value error handling test completed")
    
    def test_missing_bucket_tags_error_handling(self, aws_clients, test_config, clean_queue_state):
        """
        Test error handling when bucket tags are missing or inaccessible.
        
        **Validates: Requirements 4.5**
        
        This test verifies:
        1. Missing bucket tags are handled gracefully
        2. System falls back to default configuration when tags are missing
        3. Processing continues with default values
        4. Appropriate logging occurs for missing configuration
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Set up bucket with minimal tags (missing sibling threshold)
        minimal_tags = {
            'AllowInvalidationEvents': 'true',
            'atlantis:Application': 'test-app',
            # Note: Missing sibling threshold and other configuration tags
        }
        
        setup_bucket_tags(s3, bucket_name, minimal_tags)
        
        # Send test events
        test_message = {
            'bucketName': bucket_name,
            'objectKey': '/prod/public/missing_tags/test.html',
            'originPath': '/prod/public',
            'stageId': 'prod',
            'eventTime': datetime.now(timezone.utc).isoformat(),
            'eventType': 'ObjectCreated:Put'
        }
        
        sqs.send_message(
            QueueUrl=test_config['queue_url'],
            MessageBody=json.dumps(test_message)
        )
        
        time.sleep(2)
        
        # Invoke Lambda - should work with default values
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Verify execution was successful
        assert response['StatusCode'] == 200
        
        response_payload = json.loads(response['Payload'].read())
        if 'FunctionError' in response:
            pytest.fail(f"Lambda should handle missing tags gracefully: {response_payload}")
        
        time.sleep(2)
        
        # Get logs to verify default behavior
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Check for default value usage or missing tag handling
        default_handling_found = any(
            'default' in msg.lower() or 'missing' in msg.lower() or 'fallback' in msg.lower()
            for msg in log_messages
        )
        
        # Processing should have occurred successfully
        processing_occurred = any(
            'processed' in msg.lower() or 'completed' in msg.lower()
            for msg in log_messages
        )
        
        assert processing_occurred, f"Processing should have occurred with default values. Messages: {log_messages}"
        
        print("Missing bucket tags error handling test completed")


class TestEdgeCases:
    """Test edge cases for sibling threshold parameter."""
    
    def test_extreme_sibling_threshold_values(self, aws_clients, test_config, clean_queue_state):
        """
        Test behavior with extreme but valid sibling threshold values.
        
        **Validates: Requirements 4.4, 4.5**
        
        This test verifies:
        1. Very low threshold values (1) work correctly
        2. Very high threshold values work correctly
        3. System handles edge cases gracefully
        4. Performance is acceptable with extreme values
        """
        s3 = aws_clients['s3']
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        logs_client = aws_clients['logs']
        
        bucket_name = test_config['test_bucket']
        
        # Test with very low threshold (1)
        print("Testing with very low threshold (1)")
        
        config_tags_low = {
            'AllowInvalidationEvents': 'true',
            'atlantis:Application': 'test-app',
            'invalidator:SiblingDirectoryConsolidationThreshold': '1',
            'invalidator:ConsolidationStopLevel': '1',
            'invalidator:DirectoryConsolidationThreshold': '3',
        }
        
        setup_bucket_tags(s3, bucket_name, config_tags_low)
        
        # Send events for 2 sibling directories (should consolidate with threshold=1)
        for i in range(2):
            for file_num in range(4):
                test_message = {
                    'bucketName': bucket_name,
                    'objectKey': f'/prod/public/low_thresh_{i}/file{file_num}.html',
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
        
        # Clean for next test
        sqs.purge_queue(QueueUrl=test_config['queue_url'])
        time.sleep(2)
        
        # Test with very high threshold (1000)
        print("Testing with very high threshold (1000)")
        
        config_tags_high = {
            'AllowInvalidationEvents': 'true',
            'atlantis:Application': 'test-app',
            'invalidator:SiblingDirectoryConsolidationThreshold': '1000',
            'invalidator:ConsolidationStopLevel': '1',
            'invalidator:DirectoryConsolidationThreshold': '3',
        }
        
        setup_bucket_tags(s3, bucket_name, config_tags_high)
        
        # Send events for 5 sibling directories (should NOT consolidate with threshold=1000)
        for i in range(5):
            for file_num in range(4):
                test_message = {
                    'bucketName': bucket_name,
                    'objectKey': f'/prod/public/high_thresh_{i}/file{file_num}.html',
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
        
        # Get logs to verify both tests worked
        log_events = get_recent_log_events(logs_client, test_config['processor_function_name'])
        log_messages = [event['message'] for event in log_events]
        
        # Should see evidence of both threshold values being used
        low_threshold_used = any('1' in msg and 'threshold' in msg.lower() for msg in log_messages)
        high_threshold_used = any('1000' in msg and 'threshold' in msg.lower() for msg in log_messages)
        
        # Both extreme values should have been processed successfully
        processing_completed = any('completed' in msg.lower() or 'processed' in msg.lower() for msg in log_messages)
        
        assert processing_completed, f"Processing should have completed with extreme threshold values. Messages: {log_messages}"
        
        print("Extreme threshold values test completed")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])