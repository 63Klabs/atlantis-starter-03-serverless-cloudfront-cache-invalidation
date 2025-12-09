# IAM Permissions Integration Testing Guide

## Overview

This guide explains how to test IAM permissions for the Multi-Bucket CloudFront Invalidation Service. The integration tests verify that Lambda functions have the correct permissions to interact with AWS services as defined in the CloudFormation template.

## Test Architecture

### Test Strategy

The integration tests follow a **real AWS service** approach:
- Tests run against actual deployed Lambda functions
- Tests interact with real AWS services (SQS, S3, CloudFront)
- Tests verify IAM policies work as designed
- Tests validate tag-based IAM conditions

### Why Integration Tests for IAM?

IAM permissions cannot be fully tested with mocks because:
1. **Policy Evaluation**: AWS IAM policy evaluation is complex and includes conditions, resource patterns, and tag-based access control
2. **Service Integration**: Permissions must work across multiple AWS services
3. **Tag Conditions**: Tag-based IAM conditions require real resource tags
4. **Real-World Validation**: Only real AWS API calls can verify permissions work in production

## Test Coverage

### Requirements Validated

The integration tests validate the following requirements from the design document:

#### Requirement 12.1: Ingestor SQS Permissions
- **Test**: `test_ingestor_can_send_to_sqs`
- **Validates**: Ingestor Lambda can send messages to the Event Queue
- **IAM Action**: `sqs:SendMessage`
- **Resource Scope**: Event Queue ARN only

#### Requirement 12.2: Processor SQS Permissions
- **Tests**: 
  - `test_processor_can_read_from_sqs`
  - `test_processor_can_delete_from_sqs`
- **Validates**: Processor Lambda can receive and delete messages from Event Queue
- **IAM Actions**: `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes`
- **Resource Scope**: Event Queue ARN only

#### Requirement 12.3: Processor S3 Permissions
- **Test**: `test_processor_can_read_s3_bucket_tags`
- **Validates**: Processor Lambda can read S3 bucket tags
- **IAM Action**: `s3:GetBucketTagging`
- **Resource Scope**: Buckets matching Prefix pattern
- **Condition**: `aws:ResourceTag/AllowInvalidationEvents = true`

#### Requirement 12.4: Processor CloudFront Permissions
- **Tests**:
  - `test_processor_can_list_cloudfront_distributions`
  - `test_processor_can_get_cloudfront_distribution`
  - `test_processor_can_create_invalidation_on_tagged_distribution`
- **Validates**: Processor Lambda can list, get, and create invalidations
- **IAM Actions**: 
  - `cloudfront:ListDistributions` (global)
  - `cloudfront:GetDistribution` (global)
  - `cloudfront:CreateInvalidation` (with tag condition)
- **Condition**: `aws:ResourceTag/AllowCloudFrontCacheInvalidation = true`

### Tag-Based IAM Conditions

Two tests specifically validate tag-based IAM conditions:

1. **S3 Tag Condition** (`test_s3_tag_condition_enforcement`)
   - Verifies `AllowInvalidationEvents=true` tag is required
   - Tests that Processor can only read tags from properly tagged buckets

2. **CloudFront Tag Condition** (`test_cloudfront_tag_condition_enforcement`)
   - Verifies `AllowCloudFrontCacheInvalidation=true` tag is required
   - Tests that Processor can only create invalidations on properly tagged distributions

## Running the Tests

### Quick Start

Use the provided shell script:

```bash
cd application-infrastructure/src/tests/integration
./run_integration_tests.sh
```

The script will:
1. Prompt for CloudFormation stack name
2. Fetch Lambda function names and queue URL from stack outputs
3. Prompt for test bucket and distribution
4. Verify test resources exist and have correct tags
5. Set environment variables
6. Run the integration tests

### Manual Setup

If you prefer to set up manually:

```bash
# Set required environment variables
export RUN_INTEGRATION_TESTS=1
export INGESTOR_FUNCTION_NAME="acme-project-prod-Ingestor"
export PROCESSOR_FUNCTION_NAME="acme-project-prod-Processor"
export TEST_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/acme-project-prod-EventQueue"
export TEST_BUCKET_NAME="acme-test-bucket"
export TEST_DISTRIBUTION_ID="E1234ABCD5678"

# Run tests
cd application-infrastructure
pytest src/tests/integration/test_iam_permissions.py -v
```

### Running Specific Test Classes

```bash
# Test only Ingestor permissions
pytest src/tests/integration/test_iam_permissions.py::TestIngestorIAMPermissions -v

# Test only Processor permissions
pytest src/tests/integration/test_iam_permissions.py::TestProcessorIAMPermissions -v

# Test only tag-based conditions
pytest src/tests/integration/test_iam_permissions.py::TestTagBasedIAMConditions -v
```

### Running Individual Tests

```bash
# Test SQS send permission
pytest src/tests/integration/test_iam_permissions.py::TestIngestorIAMPermissions::test_ingestor_can_send_to_sqs -v

# Test CloudFront invalidation permission
pytest src/tests/integration/test_iam_permissions.py::TestProcessorIAMPermissions::test_processor_can_create_invalidation_on_tagged_distribution -v
```

## Test Resource Setup

### 1. Deploy CloudFormation Stack

Deploy the application stack first:

```bash
sam build
sam deploy --guided
```

### 2. Create Test S3 Bucket

Create a bucket for testing (or use an existing one):

```bash
# Create bucket
aws s3 mb s3://your-test-bucket-name

# Add required tag
aws s3api put-bucket-tagging \
  --bucket your-test-bucket-name \
  --tagging 'TagSet=[{Key=AllowInvalidationEvents,Value=true}]'

# Verify tag
aws s3api get-bucket-tagging --bucket your-test-bucket-name
```

### 3. Tag CloudFront Distribution

Tag an existing CloudFront distribution for testing:

```bash
# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Tag the distribution
aws cloudfront tag-resource \
  --resource arn:aws:cloudfront::${ACCOUNT_ID}:distribution/YOUR_DISTRIBUTION_ID \
  --tags 'Items=[
    {Key=AllowCloudFrontCacheInvalidation,Value=true},
    {Key=atlantis:ApplicationDeploymentId,Value=your-bucket-app-prod}
  ]'

# Verify tags
aws cloudfront list-tags-for-resource \
  --resource arn:aws:cloudfront::${ACCOUNT_ID}:distribution/YOUR_DISTRIBUTION_ID
```

### 4. Configure S3 Event Notification (Optional)

For end-to-end testing, configure S3 to send events to the Ingestor Lambda:

```bash
# Get Ingestor Lambda ARN from stack outputs
INGESTOR_ARN=$(aws cloudformation describe-stacks \
  --stack-name your-stack-name \
  --query 'Stacks[0].Outputs[?OutputKey==`IngestorFunctionArn`].OutputValue' \
  --output text)

# Create notification configuration
cat > notification.json <<EOF
{
  "LambdaFunctionConfigurations": [
    {
      "LambdaFunctionArn": "$INGESTOR_ARN",
      "Events": ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "prod/public/"}
          ]
        }
      }
    }
  ]
}
EOF

# Apply notification configuration
aws s3api put-bucket-notification-configuration \
  --bucket your-test-bucket-name \
  --notification-configuration file://notification.json
```

## Understanding Test Results

### Successful Test Output

```
test_iam_permissions.py::TestIngestorIAMPermissions::test_ingestor_can_send_to_sqs PASSED
test_iam_permissions.py::TestProcessorIAMPermissions::test_processor_can_read_from_sqs PASSED
test_iam_permissions.py::TestProcessorIAMPermissions::test_processor_can_delete_from_sqs PASSED
...
```

### Common Failure Scenarios

#### 1. AccessDenied Errors

```
AccessDenied: User: arn:aws:sts::123456789012:assumed-role/RoleName/FunctionName 
is not authorized to perform: sqs:SendMessage on resource: arn:aws:sqs:...
```

**Cause**: IAM policy is missing or incorrectly scoped
**Solution**: Verify IAM policy in CloudFormation template matches requirements

#### 2. Missing Tags

```
AssertionError: Test bucket must have AllowInvalidationEvents tag
```

**Cause**: Test resource doesn't have required tag
**Solution**: Add the required tag to the test resource

#### 3. Tag Condition Failures

```
AccessDenied: ... with an explicit deny in a resource-based policy
```

**Cause**: Tag-based IAM condition is blocking access
**Solution**: Verify resource has correct tag value (must be exactly "true")

#### 4. Resource Not Found

```
NoSuchBucket: The specified bucket does not exist
```

**Cause**: Test resource doesn't exist or name is incorrect
**Solution**: Verify resource exists and environment variable is correct

## Debugging Failed Tests

### 1. Check CloudWatch Logs

View Lambda execution logs:

```bash
# Ingestor logs
aws logs tail /aws/lambda/your-prefix-project-stage-Ingestor --follow

# Processor logs
aws logs tail /aws/lambda/your-prefix-project-stage-Processor --follow
```

### 2. Verify IAM Policies

Check the actual IAM policies attached to Lambda execution roles:

```bash
# Get role name from CloudFormation
ROLE_NAME=$(aws cloudformation describe-stack-resources \
  --stack-name your-stack-name \
  --logical-resource-id ProcessorExecutionRole \
  --query 'StackResources[0].PhysicalResourceId' \
  --output text)

# Get inline policies
aws iam list-role-policies --role-name $ROLE_NAME

# Get policy document
aws iam get-role-policy \
  --role-name $ROLE_NAME \
  --policy-name your-policy-name
```

### 3. Test IAM Policy Simulator

Use AWS IAM Policy Simulator to test specific actions:

```bash
# Simulate CloudFront CreateInvalidation
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/RoleName \
  --action-names cloudfront:CreateInvalidation \
  --resource-arns arn:aws:cloudfront::123456789012:distribution/DISTID
```

### 4. Verify Resource Tags

Check that test resources have correct tags:

```bash
# S3 bucket tags
aws s3api get-bucket-tagging --bucket your-test-bucket

# CloudFront distribution tags
aws cloudfront list-tags-for-resource \
  --resource arn:aws:cloudfront::ACCOUNT_ID:distribution/DIST_ID
```

## Cost Considerations

Integration tests interact with real AWS services and incur costs:

| Service | Cost Factor | Mitigation |
|---------|-------------|------------|
| Lambda Invocations | Per invocation + duration | Run tests sparingly |
| SQS Messages | Per request | Tests send minimal messages |
| CloudFront Invalidations | First 1000/month free, then $0.005 each | Tests create 1-2 invalidations |
| CloudWatch Logs | Storage + ingestion | Use short retention for test logs |

**Estimated cost per test run**: < $0.01 (assuming within free tier)

## Best Practices

### 1. Use Dedicated Test Resources

- Create separate S3 buckets for testing
- Use test CloudFront distributions (not production)
- Tag test resources clearly (e.g., `Environment=test`)

### 2. Clean Up After Tests

```bash
# Purge SQS queue
aws sqs purge-queue --queue-url $TEST_QUEUE_URL

# Delete test objects from S3
aws s3 rm s3://test-bucket/prod/public/test-iam-permissions.txt
```

### 3. Run Tests in CI/CD

Include integration tests in your deployment pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run Integration Tests
  env:
    RUN_INTEGRATION_TESTS: 1
    INGESTOR_FUNCTION_NAME: ${{ secrets.INGESTOR_FUNCTION_NAME }}
    PROCESSOR_FUNCTION_NAME: ${{ secrets.PROCESSOR_FUNCTION_NAME }}
    TEST_QUEUE_URL: ${{ secrets.TEST_QUEUE_URL }}
    TEST_BUCKET_NAME: ${{ secrets.TEST_BUCKET_NAME }}
    TEST_DISTRIBUTION_ID: ${{ secrets.TEST_DISTRIBUTION_ID }}
  run: |
    pytest src/tests/integration/test_iam_permissions.py -v
```

### 4. Monitor Test Execution

- Check CloudWatch Logs for Lambda errors
- Monitor SQS queue depth
- Track CloudFront invalidation status
- Review X-Ray traces for performance issues

## Troubleshooting Guide

### Tests Are Skipped

**Problem**: All tests show as "SKIPPED"

**Solutions**:
1. Set `RUN_INTEGRATION_TESTS=1`
2. Verify all environment variables are set
3. Check AWS credentials are configured

### Lambda Invocation Fails

**Problem**: `Lambda invocation failed with status code 403`

**Solutions**:
1. Verify AWS credentials have `lambda:InvokeFunction` permission
2. Check Lambda function exists and name is correct
3. Verify Lambda function is in the same region as your AWS profile

### SQS Permission Denied

**Problem**: `AccessDenied on sqs:SendMessage`

**Solutions**:
1. Check IAM policy in CloudFormation template
2. Verify policy resource ARN matches queue ARN
3. Ensure no explicit deny statements in policies

### CloudFront Tag Condition Fails

**Problem**: `AccessDenied when creating invalidation`

**Solutions**:
1. Verify distribution has `AllowCloudFrontCacheInvalidation=true` tag
2. Check tag value is exactly "true" (case-sensitive)
3. Ensure IAM policy condition matches tag key exactly

## Additional Resources

- [AWS IAM Policy Evaluation Logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html)
- [AWS IAM Policy Simulator](https://policysim.aws.amazon.com/)
- [CloudFormation IAM Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html#creds)
- [pytest Documentation](https://docs.pytest.org/)

## Support

For issues or questions:
1. Check CloudWatch Logs for detailed error messages
2. Review IAM policies in CloudFormation template
3. Verify test resources have correct tags
4. Consult AWS documentation for specific service errors
