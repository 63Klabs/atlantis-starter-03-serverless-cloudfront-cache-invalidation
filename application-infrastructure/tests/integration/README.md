# Integration Tests

This directory contains integration tests that verify the deployed CloudFormation stack works correctly with real AWS services.

## Prerequisites

1. **Deployed CloudFormation Stack**: The application must be deployed to AWS
2. **AWS Credentials**: Configured with appropriate permissions
3. **Test Resources**:
   - S3 bucket with `AllowInvalidationEvents=true` tag
   - CloudFront distribution with `AllowCloudFrontCacheInvalidation=true` tag
   - CloudFront distribution with `atlantis:ApplicationDeploymentId` tag matching pattern

## Running Integration Tests

### Setup Environment Variables

```bash
export RUN_INTEGRATION_TESTS=1
export INGESTOR_FUNCTION_NAME="your-prefix-project-stage-Ingestor"
export PROCESSOR_FUNCTION_NAME="your-prefix-project-stage-Processor"
export TEST_QUEUE_URL="https://sqs.region.amazonaws.com/account/queue-name"
export TEST_BUCKET_NAME="your-test-bucket-name"
export TEST_DISTRIBUTION_ID="E1234ABCD5678"
export TRACKING_TABLE="your-prefix-project-stage-WindowTracking"
```

### Run All Integration Tests

```bash
cd application-infrastructure
pytest tests/integration/ -v
```

### Run Specific Test Files

```bash
# IAM permissions tests
pytest tests/integration/test_iam_permissions.py -v

# DynamoDB window tracking tests
pytest tests/integration/test_dynamodb_window_tracking.py -v

# End-to-end flow tests
pytest tests/integration/test_end_to_end.py -v
```

### Run Specific Test Classes

```bash
# Test only Ingestor IAM permissions
pytest tests/integration/test_iam_permissions.py::TestIngestorIAMPermissions -v

# Test only Processor IAM permissions
pytest tests/integration/test_iam_permissions.py::TestProcessorIAMPermissions -v

# Test only tag-based conditions
pytest tests/integration/test_iam_permissions.py::TestTagBasedIAMConditions -v

# Test only window creation
pytest tests/integration/test_dynamodb_window_tracking.py::TestWindowCreation -v

# Test only duplicate prevention
pytest tests/integration/test_dynamodb_window_tracking.py::TestDuplicateSchedulePrevention -v

# Test only window closure
pytest tests/integration/test_dynamodb_window_tracking.py::TestWindowClosure -v

# Test only TTL cleanup
pytest tests/integration/test_dynamodb_window_tracking.py::TestTTLCleanup -v
```

## Test Coverage

### test_iam_permissions.py

Tests IAM permissions for Lambda functions:

- **Ingestor Permissions**:
  - ✓ Can send messages to SQS
  
- **Processor Permissions**:
  - ✓ Can read messages from SQS
  - ✓ Can delete messages from SQS
  - ✓ Can read S3 bucket tags
  - ✓ Can list CloudFront distributions
  - ✓ Can get CloudFront distribution details
  - ✓ Can create invalidations on tagged distributions
  
- **Tag-Based IAM Conditions**:
  - ✓ S3 GetBucketTagging enforces AllowInvalidationEvents tag
  - ✓ CloudFront CreateInvalidation enforces AllowCloudFrontCacheInvalidation tag

### test_dynamodb_window_tracking.py

Tests DynamoDB window tracking mechanism:

- **Window Creation**:
  - ✓ Create window on first event
  - ✓ Window has correct attributes (status, timestamps, TTL)
  
- **Duplicate Schedule Prevention**:
  - ✓ Prevent duplicate schedule creation
  - ✓ Handle concurrent create attempts correctly
  
- **Window Closure**:
  - ✓ Close window after processing
  - ✓ Handle closing nonexistent window
  - ✓ Create new window after closure
  
- **TTL Cleanup**:
  - ✓ TTL attribute is set correctly
  - ✓ TTL configuration on table
  - ✓ Closed windows retain TTL
  
- **Edge Cases**:
  - ✓ Check active window when none exists
  - ✓ Window ID is always 'current'
  - ✓ Window timestamps are monotonic

### test_end_to_end.py

Tests complete event flow:
- S3 event → Ingestor → SQS → Processor → CloudFront invalidation

## Setting Up Test Resources

### Create Test S3 Bucket

```bash
aws s3 mb s3://your-test-bucket-name
aws s3api put-bucket-tagging \
  --bucket your-test-bucket-name \
  --tagging 'TagSet=[{Key=AllowInvalidationEvents,Value=true}]'
```

### Tag CloudFront Distribution

```bash
aws cloudfront tag-resource \
  --resource arn:aws:cloudfront::ACCOUNT_ID:distribution/DISTRIBUTION_ID \
  --tags 'Items=[
    {Key=AllowCloudFrontCacheInvalidation,Value=true},
    {Key=atlantis:ApplicationDeploymentId,Value=bucket-app-prod}
  ]'
```

### Get Stack Outputs

```bash
# Get Lambda function names
aws cloudformation describe-stacks \
  --stack-name your-stack-name \
  --query 'Stacks[0].Outputs[?OutputKey==`IngestorFunctionArn`].OutputValue' \
  --output text

# Get Queue URL
aws cloudformation describe-stacks \
  --stack-name your-stack-name \
  --query 'Stacks[0].Outputs[?OutputKey==`EventQueueUrl`].OutputValue' \
  --output text
```

## Troubleshooting

### Tests are Skipped

If tests are skipped, ensure:
1. `RUN_INTEGRATION_TESTS=1` is set
2. All required environment variables are set
3. AWS credentials are configured

### Permission Denied Errors

If tests fail with permission errors:
1. Verify the Lambda execution roles have correct policies
2. Check that test resources have required tags
3. Verify IAM policy conditions match resource tags

### No Messages in Queue

If SQS tests fail:
1. Check CloudWatch Logs for Ingestor Lambda errors
2. Verify S3 bucket event notification is configured
3. Check that test bucket has correct tags

### CloudFront Invalidation Fails

If invalidation tests fail:
1. Verify distribution has `AllowCloudFrontCacheInvalidation=true` tag
2. Check that distribution has correct `atlantis:ApplicationDeploymentId` tag
3. Verify CloudFront distribution is in "Deployed" state

## Cost Considerations

Integration tests interact with real AWS services and may incur costs:
- Lambda invocations
- SQS messages
- CloudFront invalidations (first 1000/month free)
- CloudWatch Logs storage

Run integration tests sparingly and clean up test resources after testing.

## Cleanup

After running tests, you may want to:

1. **Purge SQS Queue**:
   ```bash
   aws sqs purge-queue --queue-url $TEST_QUEUE_URL
   ```

2. **Check CloudWatch Logs**:
   ```bash
   aws logs tail /aws/lambda/your-function-name --follow
   ```

3. **Monitor CloudFront Invalidations**:
   ```bash
   aws cloudfront list-invalidations --distribution-id $TEST_DISTRIBUTION_ID
   ```
