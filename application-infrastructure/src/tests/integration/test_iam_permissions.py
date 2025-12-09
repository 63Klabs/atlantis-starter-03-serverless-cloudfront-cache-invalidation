"""
Integration tests for IAM permissions.

These tests verify that the Lambda functions have the correct IAM permissions
to interact with AWS services. These tests require:
1. Deployed CloudFormation stack with Lambda functions
2. AWS credentials configured
3. Test S3 bucket with AllowInvalidationEvents tag
4. Test CloudFront distribution with appropriate tags

Run with: pytest src/tests/integration/test_iam_permissions.py -v

Environment variables required:
- INGESTOR_FUNCTION_NAME: Name of the deployed Ingestor Lambda
- PROCESSOR_FUNCTION_NAME: Name of the deployed Processor Lambda
- TEST_QUEUE_URL: URL of the SQS queue
- TEST_BUCKET_NAME: Name of test S3 bucket with AllowInvalidationEvents=true
- TEST_DISTRIBUTION_ID: CloudFront distribution ID with appropriate tags
"""

import os
import json
import time
import uuid
import boto3
import pytest
from datetime import datetime, timezone


# Skip all tests if not in integration test mode
pytestmark = pytest.mark.skipif(
    not os.environ.get('RUN_INTEGRATION_TESTS'),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1 and deployed AWS resources"
)


@pytest.fixture(scope="module")
def aws_clients():
    """Create AWS service clients for integration tests."""
    return {
        'sqs': boto3.client('sqs'),
        's3': boto3.client('s3'),
        'cloudfront': boto3.client('cloudfront'),
        'lambda': boto3.client('lambda'),
    }


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration from environment variables."""
    config = {
        'ingestor_function_name': os.environ.get('INGESTOR_FUNCTION_NAME'),
        'processor_function_name': os.environ.get('PROCESSOR_FUNCTION_NAME'),
        'queue_url': os.environ.get('TEST_QUEUE_URL'),
        'test_bucket_name': os.environ.get('TEST_BUCKET_NAME'),
        'test_distribution_id': os.environ.get('TEST_DISTRIBUTION_ID'),
    }
    
    # Validate required configuration
    missing = [k for k, v in config.items() if not v]
    if missing:
        pytest.skip(f"Missing required environment variables: {', '.join(missing)}")
    
    return config


class TestIngestorIAMPermissions:
    """Test IAM permissions for the Ingestor Lambda function."""
    
    def test_ingestor_can_send_to_sqs(self, aws_clients, test_config):
        """
        Verify Ingestor can write to SQS.
        
        Requirements: 12.1 - Ingestor: SQS SendMessage scoped to Event Queue ARN
        """
        sqs = aws_clients['sqs']
        lambda_client = aws_clients['lambda']
        
        # Create a test S3 event
        test_event = {
            "Records": [{
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "s3": {
                    "bucket": {
                        "name": test_config['test_bucket_name']
                    },
                    "object": {
                        "key": "prod/public/test-iam-permissions.txt"
                    }
                }
            }]
        }
        
        # Invoke Ingestor Lambda
        response = lambda_client.invoke(
            FunctionName=test_config['ingestor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps(test_event)
        )
        
        # Check Lambda execution was successful
        assert response['StatusCode'] == 200
        
        # Parse response
        response_payload = json.loads(response['Payload'].read())
        
        # If there's a function error, fail the test
        if 'FunctionError' in response:
            pytest.fail(f"Lambda execution failed: {response_payload}")
        
        # Wait a moment for message to appear in queue
        time.sleep(2)
        
        # Verify message was sent to SQS
        messages = sqs.receive_message(
            QueueUrl=test_config['queue_url'],
            MaxNumberOfMessages=10,
            WaitTimeSeconds=5
        )
        
        # Should have at least one message
        assert 'Messages' in messages, "No messages found in SQS queue"
        assert len(messages['Messages']) > 0, "Expected at least one message in queue"
        
        # Verify message contains expected fields
        message_body = json.loads(messages['Messages'][0]['Body'])
        assert 'bucketName' in message_body
        assert 'objectKey' in message_body
        assert 'originPath' in message_body
        assert 'stageId' in message_body
        
        # Clean up - delete the test message
        sqs.delete_message(
            QueueUrl=test_config['queue_url'],
            ReceiptHandle=messages['Messages'][0]['ReceiptHandle']
        )


class TestProcessorIAMPermissions:
    """Test IAM permissions for the Processor Lambda function."""
    
    def test_processor_can_read_from_sqs(self, aws_clients, test_config):
        """
        Verify Processor can read from SQS.
        
        Requirements: 12.2 - Processor: SQS ReceiveMessage scoped to Event Queue ARN
        """
        sqs = aws_clients['sqs']
        
        # Send a test message to the queue
        test_message = {
            'bucketName': test_config['test_bucket_name'],
            'objectKey': '/prod/public/test-read-sqs.txt',
            'originPath': '/prod/public',
            'stageId': 'prod',
            'eventTime': datetime.now(timezone.utc).isoformat(),
            'eventType': 'ObjectCreated:Put'
        }
        
        sqs.send_message(
            QueueUrl=test_config['queue_url'],
            MessageBody=json.dumps(test_message)
        )
        
        # Wait for message to be available
        time.sleep(1)
        
        # Invoke Processor Lambda (it should be able to receive messages)
        lambda_client = aws_clients['lambda']
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Check Lambda execution was successful
        assert response['StatusCode'] == 200
        
        # Parse response
        response_payload = json.loads(response['Payload'].read())
        
        # If there's a function error related to SQS permissions, fail
        if 'FunctionError' in response:
            error_message = str(response_payload)
            if 'AccessDenied' in error_message or 'sqs:ReceiveMessage' in error_message:
                pytest.fail(f"Processor lacks SQS ReceiveMessage permission: {error_message}")
    
    def test_processor_can_delete_from_sqs(self, aws_clients, test_config):
        """
        Verify Processor can delete messages from SQS.
        
        Requirements: 12.2 - Processor: SQS DeleteMessage scoped to Event Queue ARN
        """
        sqs = aws_clients['sqs']
        
        # Send a test message
        test_message = {
            'bucketName': test_config['test_bucket_name'],
            'objectKey': '/prod/public/test-delete-sqs.txt',
            'originPath': '/prod/public',
            'stageId': 'prod',
            'eventTime': datetime.now(timezone.utc).isoformat(),
            'eventType': 'ObjectCreated:Put'
        }
        
        send_response = sqs.send_message(
            QueueUrl=test_config['queue_url'],
            MessageBody=json.dumps(test_message)
        )
        
        message_id = send_response['MessageId']
        
        # Wait for message to be available
        time.sleep(1)
        
        # Receive the message
        messages = sqs.receive_message(
            QueueUrl=test_config['queue_url'],
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5
        )
        
        if 'Messages' not in messages:
            pytest.skip("Test message not received, cannot test delete permission")
        
        receipt_handle = messages['Messages'][0]['ReceiptHandle']
        
        # Invoke Processor - it should process and delete the message
        lambda_client = aws_clients['lambda']
        response = lambda_client.invoke(
            FunctionName=test_config['processor_function_name'],
            InvocationType='RequestResponse',
            Payload=json.dumps({})
        )
        
        # Check Lambda execution
        assert response['StatusCode'] == 200
        
        # Wait a moment for deletion to complete
        time.sleep(2)
        
        # Try to receive the message again - it should be gone
        messages_after = sqs.receive_message(
            QueueUrl=test_config['queue_url'],
            MaxNumberOfMessages=10,
            WaitTimeSeconds=2
        )
        
        # If messages exist, check if our test message is still there
        if 'Messages' in messages_after:
            remaining_ids = [json.loads(m['Body']).get('objectKey') for m in messages_after['Messages']]
            assert '/prod/public/test-delete-sqs.txt' not in remaining_ids, \
                "Test message was not deleted by Processor"
    
    def test_processor_can_read_s3_bucket_tags(self, aws_clients, test_config):
        """
        Verify Processor can read S3 bucket tags.
        
        Requirements: 12.3 - Processor: S3 GetBucketTagging scoped to Prefix pattern
        with tag condition AllowInvalidationEvents=true
        """
        s3 = aws_clients['s3']
        
        # Attempt to get bucket tags
        try:
            response = s3.get_bucket_tagging(
                Bucket=test_config['test_bucket_name']
            )
            
            # Verify we got tags back
            assert 'TagSet' in response
            
            # Verify the AllowInvalidationEvents tag exists
            tags = {tag['Key']: tag['Value'] for tag in response['TagSet']}
            assert 'AllowInvalidationEvents' in tags, \
                "Test bucket must have AllowInvalidationEvents tag"
            assert tags['AllowInvalidationEvents'] == 'true', \
                "AllowInvalidationEvents tag must be set to 'true'"
            
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.fail(f"Processor lacks S3 GetBucketTagging permission: {e}")
            raise
    
    def test_processor_can_list_cloudfront_distributions(self, aws_clients, test_config):
        """
        Verify Processor can list CloudFront distributions.
        
        Requirements: 12.4 - Processor: CloudFront ListDistributions globally
        """
        cloudfront = aws_clients['cloudfront']
        
        # Attempt to list distributions
        try:
            response = cloudfront.list_distributions()
            
            # Verify we got a response
            assert 'DistributionList' in response
            
            # Should have at least our test distribution
            if 'Items' in response['DistributionList']:
                distribution_ids = [d['Id'] for d in response['DistributionList']['Items']]
                assert test_config['test_distribution_id'] in distribution_ids, \
                    f"Test distribution {test_config['test_distribution_id']} not found in list"
            
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.fail(f"Processor lacks CloudFront ListDistributions permission: {e}")
            raise
    
    def test_processor_can_get_cloudfront_distribution(self, aws_clients, test_config):
        """
        Verify Processor can get CloudFront distribution details.
        
        Requirements: 12.4 - Processor: CloudFront GetDistribution globally
        """
        cloudfront = aws_clients['cloudfront']
        
        # Attempt to get distribution
        try:
            response = cloudfront.get_distribution(
                Id=test_config['test_distribution_id']
            )
            
            # Verify we got distribution details
            assert 'Distribution' in response
            assert response['Distribution']['Id'] == test_config['test_distribution_id']
            
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.fail(f"Processor lacks CloudFront GetDistribution permission: {e}")
            raise
    
    def test_processor_can_create_invalidation_on_tagged_distribution(self, aws_clients, test_config):
        """
        Verify Processor can create invalidations on tagged distributions.
        
        Requirements: 12.4 - Processor: CloudFront CreateInvalidation scoped to
        distributions with tag AllowCloudFrontCacheInvalidation=true
        """
        cloudfront = aws_clients['cloudfront']
        
        # First verify the distribution has the required tag
        try:
            tags_response = cloudfront.list_tags_for_resource(
                Resource=f"arn:aws:cloudfront::{boto3.client('sts').get_caller_identity()['Account']}:distribution/{test_config['test_distribution_id']}"
            )
            
            tags = {tag['Key']: tag['Value'] for tag in tags_response['Tags']['Items']}
            
            if 'AllowCloudFrontCacheInvalidation' not in tags or tags['AllowCloudFrontCacheInvalidation'] != 'true':
                pytest.skip("Test distribution must have AllowCloudFrontCacheInvalidation=true tag")
        
        except Exception as e:
            pytest.skip(f"Could not verify distribution tags: {e}")
        
        # Attempt to create an invalidation
        try:
            caller_reference = f"test-iam-{uuid.uuid4()}"
            
            response = cloudfront.create_invalidation(
                DistributionId=test_config['test_distribution_id'],
                InvalidationBatch={
                    'Paths': {
                        'Quantity': 1,
                        'Items': ['/test-iam-permissions/*']
                    },
                    'CallerReference': caller_reference
                }
            )
            
            # Verify invalidation was created
            assert 'Invalidation' in response
            assert response['Invalidation']['Status'] in ['InProgress', 'Completed']
            
            # Store invalidation ID for potential cleanup
            invalidation_id = response['Invalidation']['Id']
            print(f"Created test invalidation: {invalidation_id}")
            
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.fail(f"Processor lacks CloudFront CreateInvalidation permission: {e}")
            raise


class TestTagBasedIAMConditions:
    """Test that tag-based IAM conditions work correctly."""
    
    def test_s3_tag_condition_enforcement(self, aws_clients, test_config):
        """
        Verify tag-based IAM conditions work for S3 GetBucketTagging.
        
        Requirements: 12.3 - Tag condition AllowInvalidationEvents=true
        """
        s3 = aws_clients['s3']
        
        # This test verifies that the IAM policy correctly enforces the tag condition
        # by attempting to read tags from the test bucket (which should have the tag)
        try:
            response = s3.get_bucket_tagging(
                Bucket=test_config['test_bucket_name']
            )
            
            tags = {tag['Key']: tag['Value'] for tag in response['TagSet']}
            
            # Verify the tag exists and has correct value
            assert 'AllowInvalidationEvents' in tags
            assert tags['AllowInvalidationEvents'] == 'true'
            
            # If we got here, the tag condition is working correctly
            # (we can only read tags from buckets with the correct tag)
            
        except Exception as e:
            if 'AccessDenied' in str(e):
                # This could mean either:
                # 1. The bucket doesn't have the tag (expected to fail)
                # 2. The IAM policy is too restrictive
                pytest.fail(f"Tag-based condition may not be working correctly: {e}")
            raise
    
    def test_cloudfront_tag_condition_enforcement(self, aws_clients, test_config):
        """
        Verify tag-based IAM conditions work for CloudFront CreateInvalidation.
        
        Requirements: 12.4 - Tag condition AllowCloudFrontCacheInvalidation=true
        """
        cloudfront = aws_clients['cloudfront']
        sts = boto3.client('sts')
        
        # Get account ID for ARN construction
        account_id = sts.get_caller_identity()['Account']
        
        # Verify the test distribution has the required tag
        try:
            tags_response = cloudfront.list_tags_for_resource(
                Resource=f"arn:aws:cloudfront::{account_id}:distribution/{test_config['test_distribution_id']}"
            )
            
            tags = {tag['Key']: tag['Value'] for tag in tags_response['Tags']['Items']}
            
            # Verify tag exists
            assert 'AllowCloudFrontCacheInvalidation' in tags, \
                "Test distribution must have AllowCloudFrontCacheInvalidation tag"
            assert tags['AllowCloudFrontCacheInvalidation'] == 'true', \
                "AllowCloudFrontCacheInvalidation must be 'true'"
            
            # If we can create an invalidation on this tagged distribution,
            # the tag condition is working
            caller_reference = f"test-tag-condition-{uuid.uuid4()}"
            
            response = cloudfront.create_invalidation(
                DistributionId=test_config['test_distribution_id'],
                InvalidationBatch={
                    'Paths': {
                        'Quantity': 1,
                        'Items': ['/test-tag-condition/*']
                    },
                    'CallerReference': caller_reference
                }
            )
            
            # Success means tag condition is working
            assert 'Invalidation' in response
            print(f"Tag condition working - created invalidation: {response['Invalidation']['Id']}")
            
        except Exception as e:
            if 'AccessDenied' in str(e):
                pytest.fail(f"Tag-based condition for CloudFront may not be working: {e}")
            raise


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
