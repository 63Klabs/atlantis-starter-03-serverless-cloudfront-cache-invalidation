# Backward Compatibility Test Guide

## Overview

This guide explains how to run the backward compatibility tests for the origin-path-pattern feature. These tests verify that the enhanced system with the new `OriginPathPattern` parameter behaves identically to the previous version when using default settings.

**Validates Requirements**: 10.1, 10.2, 10.3, 10.4

## Test Files

- `test_backward_compatibility.py` - Comprehensive backward compatibility tests
- `test_backward_compatibility_enhanced.py` - Enhanced upload utility compatibility tests

## Prerequisites

### 1. Deployed CloudFormation Stack

You need a deployed CloudFormation stack with **default parameters**. The key parameter for backward compatibility is:

```yaml
OriginPathPattern: "/{stageId}/public"  # Default value
```

### 2. Test Resources

- **Test S3 Bucket**: A bucket without new configuration tags (legacy bucket)
  - Must have `AllowInvalidationEvents=true` tag
  - Should NOT have `invalidator:OriginPathPattern` tag
  
- **Test CloudFront Distribution**: A distribution for testing
  - Must have `AllowCloudFrontCacheInvalidation=true` tag

### 3. Environment Variables

The following environment variables must be set:

```bash
export RUN_INTEGRATION_TESTS=1
export PROCESSOR_FUNCTION_NAME="<your-processor-function-name>"
export TEST_QUEUE_URL="<your-sqs-queue-url>"
export TEST_BUCKET_WITHOUT_CONFIG_TAGS="<your-test-bucket-name>"
export TEST_DISTRIBUTION_ID="<your-cloudfront-distribution-id>"
export DIRECTORY_CONSOLIDATION_THRESHOLD=3  # Default from CloudFormation
export CONSOLIDATION_STOP_LEVEL=1  # Default from CloudFormation
```

## Running the Tests

### Option 1: Using the Test Runner Script (Recommended)

The easiest way to run the tests is using the provided test runner script:

```bash
cd application-infrastructure/tests/integration

# Set the stack name
export STACK_NAME="your-stack-name"

# Set the test bucket (without new config tags)
export TEST_BUCKET_NAME="your-legacy-test-bucket"

# Set the test distribution
export TEST_DISTRIBUTION_ID="your-distribution-id"

# Run the backward compatibility tests
./run_integration_tests.sh tests/integration/test_backward_compatibility.py
```

The script will:
1. Fetch stack outputs automatically
2. Verify test resources exist
3. Set all required environment variables
4. Run the tests with proper configuration

### Option 2: Manual Execution

If you prefer to set environment variables manually:

```bash
# 1. Activate virtual environment
cd application-infrastructure
source .venv/bin/activate

# 2. Set environment variables
export RUN_INTEGRATION_TESTS=1
export PROCESSOR_FUNCTION_NAME="acme-cdn-invalidator-test-Processor"
export TEST_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/acme-cdn-invalidator-test-EventQueue"
export TEST_BUCKET_WITHOUT_CONFIG_TAGS="acme-test-bucket-legacy"
export TEST_DISTRIBUTION_ID="E1234567890ABC"
export DIRECTORY_CONSOLIDATION_THRESHOLD=3
export CONSOLIDATION_STOP_LEVEL=1

# 3. Run the tests
cd tests/integration
pytest test_backward_compatibility.py -v
```

## Test Coverage

### Test Classes and Scenarios

#### 1. TestExistingBucketsWithoutNewTags

Tests that existing buckets without new configuration tags continue to work:

- **test_legacy_bucket_processing**: Verifies buckets without new tags are processed successfully
- **test_legacy_consolidation_behavior**: Verifies consolidation uses default threshold (3) and stop level (1)
- **test_legacy_index_file_handling**: Verifies index.html and default.html files are handled correctly

#### 2. TestConsolidationBehaviorUnchanged

Tests that consolidation behavior remains unchanged for default configuration:

- **test_default_directory_consolidation_threshold**: Verifies default threshold value is used
- **test_default_stop_level_behavior**: Verifies default stop level is 1 (original behavior)
- **test_sibling_directory_consolidation**: Verifies sibling directories consolidate normally

#### 3. TestEnhancedSystemDeployment

Tests deployment of enhanced system over existing system:

- **test_environment_variables_present**: Verifies new environment variables are set correctly
- **test_backward_compatible_function_signature**: Verifies legacy event format is still supported
- **test_no_regression_in_error_handling**: Verifies error handling remains robust

## Expected Results

All tests should **PASS** when:

1. The stack is deployed with default `OriginPathPattern` parameter (`/{stageId}/public`)
2. Test buckets do NOT have the new `invalidator:OriginPathPattern` tag
3. The system processes events identically to the previous version
4. No new errors or warnings appear in CloudWatch Logs

### Success Indicators

✅ **Legacy bucket processing completes without errors**
✅ **Default consolidation threshold (3) is used**
✅ **Default stop level (1) is used**
✅ **Index file handling works as before**
✅ **Sibling directory consolidation works normally**
✅ **Environment variables are set correctly**
✅ **Legacy event format is supported**
✅ **Error handling is robust**

## Troubleshooting

### Tests are Skipped

**Problem**: All tests show as SKIPPED

**Solution**: Ensure `RUN_INTEGRATION_TESTS=1` is set

```bash
export RUN_INTEGRATION_TESTS=1
```

### Missing Environment Variables

**Problem**: Tests fail with "Missing required environment variables"

**Solution**: Verify all required variables are set:

```bash
echo $PROCESSOR_FUNCTION_NAME
echo $TEST_QUEUE_URL
echo $TEST_BUCKET_WITHOUT_CONFIG_TAGS
echo $TEST_DISTRIBUTION_ID
```

### Bucket Tag Issues

**Problem**: Tests fail because bucket has new configuration tags

**Solution**: Ensure test bucket has ONLY legacy tags:

```bash
# Check current tags
aws s3api get-bucket-tagging --bucket your-test-bucket

# Set only legacy tags (remove new config tags)
aws s3api put-bucket-tagging --bucket your-test-bucket \
  --tagging 'TagSet=[{Key=AllowInvalidationEvents,Value=true}]'
```

### Access Denied Errors

**Problem**: Tests fail with AccessDenied errors

**Solution**: Verify your AWS credentials have permissions for:
- Lambda function invocation
- SQS queue operations
- S3 bucket operations
- CloudWatch Logs access

### Test Failures

**Problem**: Tests fail indicating behavior has changed

**Solution**: This indicates a regression in backward compatibility. Review:
1. CloudFormation parameter defaults
2. Lambda function environment variables
3. Recent code changes that may affect default behavior
4. CloudWatch Logs for error messages

## Verification Checklist

Before running tests, verify:

- [ ] CloudFormation stack is deployed with default parameters
- [ ] `OriginPathPattern` parameter is set to `/{stageId}/public` (default)
- [ ] Test bucket exists and is accessible
- [ ] Test bucket has `AllowInvalidationEvents=true` tag
- [ ] Test bucket does NOT have `invalidator:OriginPathPattern` tag
- [ ] Test distribution exists and is accessible
- [ ] AWS credentials are configured
- [ ] All environment variables are set
- [ ] Virtual environment is activated (if running manually)

## Integration with CI/CD

To run these tests in a CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run Backward Compatibility Tests
  env:
    RUN_INTEGRATION_TESTS: 1
    PROCESSOR_FUNCTION_NAME: ${{ secrets.PROCESSOR_FUNCTION_NAME }}
    TEST_QUEUE_URL: ${{ secrets.TEST_QUEUE_URL }}
    TEST_BUCKET_WITHOUT_CONFIG_TAGS: ${{ secrets.TEST_BUCKET_LEGACY }}
    TEST_DISTRIBUTION_ID: ${{ secrets.TEST_DISTRIBUTION_ID }}
    DIRECTORY_CONSOLIDATION_THRESHOLD: 3
    CONSOLIDATION_STOP_LEVEL: 1
  run: |
    cd application-infrastructure
    source .venv/bin/activate
    pytest tests/integration/test_backward_compatibility.py -v
```

## Additional Resources

- **DEPLOYMENT_GUIDE.md**: Instructions for deploying the stack
- **TESTING_GUIDE.md**: Comprehensive testing documentation
- **README.md**: Integration test overview
- **run_integration_tests.sh**: Automated test runner script

## Support

If you encounter issues:

1. Check CloudWatch Logs for Lambda execution details
2. Verify all prerequisites are met
3. Review the troubleshooting section
4. Check the test output for specific error messages
5. Ensure the stack is deployed with default parameters

## Summary

The backward compatibility tests ensure that:

1. **Existing deployments continue to work** without any changes
2. **Default behavior is preserved** when using default parameters
3. **No regressions** are introduced by the new feature
4. **Legacy buckets** (without new tags) work exactly as before

These tests are critical for ensuring a smooth upgrade path for existing users of the CloudFront cache invalidation service.
