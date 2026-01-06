# Configuration Troubleshooting Guide

This guide provides detailed troubleshooting steps for the Multi-Bucket CloudFront Invalidation Service.

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Common Issues](#common-issues)
- [Diagnostic Commands](#diagnostic-commands)
- [Log Analysis](#log-analysis)
- [Configuration Validation](#configuration-validation)
- [Best Practices](#best-practices)

## Configuration Overview

The system supports three levels of configuration:

1. **Hardcoded Defaults** (fallback)
   - DirectoryConsolidationThreshold: 3
   - SiblingDirectoryConsolidationThreshold: 10
   - ConsolidationStopLevel: 1
   - AggregationWindowSeconds: 300

2. **CloudFormation Parameters** (system-wide defaults)
   - DirectoryConsolidationThreshold: 1-1000
   - SiblingDirectoryConsolidationThreshold: 1-1000
   - ConsolidationStopLevel: 0-20
   - AggregationWindowSeconds: 60-900

3. **S3 Bucket Tags** (per-bucket overrides)
   - `invalidator:DirectoryConsolidationThreshold`: 1-1000
   - `invalidator:SiblingDirectoryConsolidationThreshold`: 1-1000
   - `invalidator:ConsolidationStopLevel`: 0-20

## Common Issues

### Issue 1: Bucket Tags Not Being Read

**Symptoms**:
- Bucket-specific configuration not applied
- Default values used despite bucket tags being set
- No configuration logs for specific buckets

**Diagnostic Steps**:

1. **Verify bucket tags exist and are correctly formatted**:
   ```bash
   aws s3api get-bucket-tagging --bucket your-bucket-name
   ```

   Expected output:
   ```json
   {
     "TagSet": [
       {
         "Key": "AllowInvalidationEvents",
         "Value": "true"
       },
       {
         "Key": "invalidator:DirectoryConsolidationThreshold",
         "Value": "5"
       },
       {
         "Key": "invalidator:SiblingDirectoryConsolidationThreshold",
         "Value": "15"
       },
       {
         "Key": "invalidator:ConsolidationStopLevel",
         "Value": "2"
       }
     ]
   }
   ```

2. **Check IAM permissions for tag reading**:
   ```bash
   aws iam simulate-principal-policy \
     --policy-source-arn arn:aws:iam::ACCOUNT:role/PROCESSOR-ROLE \
     --action-names s3:GetBucketTagging \
     --resource-arns arn:aws:s3:::your-bucket-name
   ```

3. **Review Processor Lambda logs for tag reading errors**:
   ```
   fields @timestamp, @message, bucketName
   | filter @message like /tag.*error/ or @message like /failed.*read.*tag/
   | sort @timestamp desc
   ```

**Common Causes**:
- Missing IAM permissions for `s3:GetBucketTagging`
- Incorrect tag key names (case-sensitive)
- Bucket in different region than Lambda function
- Bucket name typos in S3 events

**Solutions**:
- Add `s3:GetBucketTagging` permission to Processor Lambda role
- Verify exact tag key spelling: `invalidator:DirectoryConsolidationThreshold`
- Ensure bucket and Lambda are in same region
- Check S3 event configuration

### Issue 2: Invalid Tag Values

**Symptoms**:
- Warning logs about invalid configuration values
- System falls back to default values
- Unexpected consolidation behavior

**Diagnostic Steps**:

1. **Check for invalid tag value warnings**:
   ```
   fields @timestamp, bucketName, tagKey, tagValue, @message
   | filter @message like /invalid.*tag.*value/
   | sort @timestamp desc
   ```

2. **Validate tag value ranges**:
   - DirectoryConsolidationThreshold: Must be 1-1000
   - SiblingDirectoryConsolidationThreshold: Must be 1-1000
   - ConsolidationStopLevel: Must be 0-20
   - Values must be numeric (no letters, spaces, or special characters)

3. **Check for common formatting issues**:
   ```bash
   # Good values
   "5"
   "100"
   "0"
   
   # Bad values
   " 5 "     # Leading/trailing spaces
   "5.0"     # Decimal points
   "five"    # Text
   ""        # Empty string
   "1001"    # Out of range
   ```

**Solutions**:
- Update bucket tags with valid numeric values within range
- Remove leading/trailing whitespace from tag values
- Use integer values only (no decimals)

### Issue 3: CloudFormation Parameters Not Applied

**Symptoms**:
- Lambda environment variables don't match CloudFormation parameters
- Default hardcoded values used instead of parameter values
- Configuration changes after stack update not taking effect

**Diagnostic Steps**:

1. **Check CloudFormation stack parameters**:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name your-stack-name \
     --query 'Stacks[0].Parameters'
   ```

2. **Verify Lambda environment variables**:
   ```bash
   aws lambda get-function-configuration \
     --function-name your-processor-function-name \
     --query 'Environment.Variables'
   ```

**Solutions**:
- Update `application-infrastructure/template-configuration.json` with correct parameter values
- Verify template.yml has correct environment variable mappings

### Issue 4: Consolidation Stop Level Not Working

**Symptoms**:
- Paths being consolidated despite stop level settings
- Unexpected consolidation behavior at certain directory depths
- Stop level prevention not logged

**Diagnostic Steps**:

1. **Check stop level prevention logs**:
   ```
   fields @timestamp, @message, paths, depth, stopLevel
   | filter @message like /consolidation prevented.*stop level/
   | sort @timestamp desc
   ```

2. **Verify path depth calculations**:
   ```
   fields @timestamp, path, calculatedDepth, rootPath
   | filter @message like /path depth calculation/
   | sort @timestamp desc
   ```

3. **Check effective stop level configuration**:
   ```
   fields @timestamp, bucketName, effectiveStopLevel, source
   | filter @message like /effective.*stop level/
   | sort @timestamp desc
   ```

**Intended Behavior**:
- Stop level 0 consolidates everything to root `/*`
- Stop level 1 allows normal consolidation (default behavior)
- Stop level 2+ prevents consolidation at that depth or shallower

**Common Issues**
- Path depth calculated incorrectly due to malformed paths

**Solutions**:
- Verify stop level value matches intended behavior
- Check path structure and root path calculation
- Review consolidation algorithm documentation

### Issue 5: Configuration Changes Not Taking Effect

**Symptoms**:
- Updated bucket tags not reflected in behavior
- CloudFormation parameter changes not applied
- Inconsistent consolidation behavior

**Diagnostic Steps**:

1. **For bucket tag changes**:
   - Changes take effect on next processing cycle (within 5 minutes)
   - Check tag update timestamp vs. last processing time
   - Verify tags were actually updated (not just attempted)
   - Ensure tags are spelled and formatted correctly

2. **For CloudFormation parameter changes**:
   - Requires CloudFormation stack update
   - Lambda functions must redeploy to pick up new environment variables
   - Check stack update status and Lambda function last modified time

3. **Check configuration resolution logs**:
   ```
   fields @timestamp, bucketName, configSource, @message
   | filter @message like /configuration.*resolved/
   | sort @timestamp desc
   ```

**Solutions**:
- Wait for next processing cycle after bucket tag changes
- Update CloudFormation stack for parameter changes
- Manually restart Lambda functions if needed
- Verify configuration changes in logs before testing

## Diagnostic Commands

### Check Current Configuration

```bash
# Get CloudFormation stack parameters
aws cloudformation describe-stacks \
  --stack-name your-stack-name \
  --query 'Stacks[0].Parameters[?ParameterKey==`DirectoryConsolidationThreshold` || ParameterKey==`SiblingDirectoryConsolidationThreshold` || ParameterKey==`ConsolidationStopLevel`]'

# Get bucket tags
aws s3api get-bucket-tagging --bucket your-bucket-name

# Get Lambda environment variables
aws lambda get-function-configuration \
  --function-name your-processor-function-name \
  --query 'Environment.Variables.{DirectoryThreshold:DIRECTORY_CONSOLIDATION_THRESHOLD,SiblingThreshold:SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,StopLevel:CONSOLIDATION_STOP_LEVEL,WindowSeconds:AGGREGATION_WINDOW_SECONDS}'
```

### Test Configuration

```bash
# Upload test file to trigger processing
aws s3 cp test.html s3://your-bucket/prod/public/mytest/test.html

# Monitor logs for configuration decisions
aws logs tail /aws/lambda/your-processor-function-name --follow
```

### Validate Permissions

```bash
# Check S3 tag reading permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT:role/your-processor-role \
  --action-names s3:GetBucketTagging \
  --resource-arns arn:aws:s3:::your-bucket-name

# Check CloudFormation describe permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT:role/your-processor-role \
  --action-names cloudformation:DescribeStacks \
  --resource-arns arn:aws:cloudformation:region:account:stack/your-stack-name/*
```

## Log Analysis

### Key Log Messages to Look For

1. **Configuration Resolution**:
   ```json
   {
     "level": "INFO",
     "message": "Effective configuration resolved",
     "bucketName": "example-bucket",
     "directoryThreshold": 5,
     "directoryThresholdSource": "tag",
     "stopLevel": 2,
     "stopLevelSource": "tag"
   }
   ```

2. **Tag Validation Warnings**:
   ```json
   {
     "level": "WARN",
     "message": "Invalid tag value for consolidation configuration",
     "bucketName": "example-bucket",
     "tagKey": "invalidator:DirectoryConsolidationThreshold",
     "tagValue": "invalid",
     "reason": "Value must be numeric between 1 and 1000",
     "fallbackValue": 3
   }
   ```

3. **Stop Level Prevention**:
   ```json
   {
     "level": "INFO",
     "message": "Consolidation prevented by stop level",
     "paths": ["/prod/public/docs/api/file1.html", "/prod/public/docs/api/file2.html"],
     "targetPath": "/prod/public/docs/api/*",
     "depth": 3,
     "stopLevel": 3,
     "reason": "Consolidation would occur at or above stop level"
   }
   ```

### CloudWatch Insights Queries

```sql
-- Find all configuration decisions
fields @timestamp, bucketName, directoryThreshold, stopLevel, source
| filter @message like /effective configuration/
| sort @timestamp desc
| limit 100

-- Find consolidation prevention events
fields @timestamp, @message, paths, depth, stopLevel
| filter @message like /consolidation prevented/
| sort @timestamp desc
| limit 50

-- Find tag validation errors
fields @timestamp, bucketName, tagKey, tagValue, reason
| filter @message like /invalid.*tag/
| sort @timestamp desc
| limit 50

-- Find configuration source breakdown
fields @timestamp, bucketName, directoryThresholdSource, stopLevelSource
| filter @message like /effective configuration/
| stats count() by directoryThresholdSource, stopLevelSource
```

## Configuration Validation

### Validation Checklist

- [ ] **CloudFormation Parameters**
  - [ ] DirectoryConsolidationThreshold: 1-1000
  - [ ] SiblingDirectoryConsolidationThreshold: 1-1000
  - [ ] ConsolidationStopLevel: 0-20
  - [ ] AggregationWindowSeconds: 60-900
  - [ ] Parameters applied to Lambda environment variables

- [ ] **S3 Bucket Tags**
  - [ ] AllowInvalidationEvents: "true" (required)
  - [ ] invalidator:DirectoryConsolidationThreshold: 1-1000 (optional)
  - [ ] invalidator:SiblingDirectoryConsolidationThreshold: 1-1000 (optional)
  - [ ] invalidator:ConsolidationStopLevel: 0-20 (optional)
  - [ ] Tag keys spelled correctly (case-sensitive)
  - [ ] Tag values are numeric strings

- [ ] **IAM Permissions**
  - [ ] s3:GetBucketTagging on target buckets
  - [ ] cloudfront:CreateInvalidation on target distributions
  - [ ] sqs:ReceiveMessage, sqs:DeleteMessage on queue
  - [ ] dynamodb:GetItem, dynamodb:PutItem on tracking table

- [ ] **Lambda Configuration**
  - [ ] Environment variables match CloudFormation parameters
  - [ ] Function has sufficient timeout (300 seconds recommended)
  - [ ] Function has sufficient memory (512 MB recommended)

### Testing Configuration

1. **Test with Known Values**:
   ```bash
   # Set bucket tags to known values
   aws s3api put-bucket-tagging \
     --bucket test-bucket \
     --tagging 'TagSet=[
       {Key=AllowInvalidationEvents,Value=true},
       {Key=invalidator:DirectoryConsolidationThreshold,Value=2},
       {Key=invalidator:SiblingDirectoryConsolidationThreshold,Value=5},
       {Key=invalidator:ConsolidationStopLevel,Value=3}
     ]'
   
   # Upload files to trigger consolidation
   aws s3 cp file1.html s3://test-bucket/prod/public/test/file1.html
   aws s3 cp file2.html s3://test-bucket/prod/public/test/file2.html
   aws s3 cp file3.html s3://test-bucket/prod/public/test/file3.html
   
   # Wait 5+ minutes and check logs for configuration usage
   ```

2. **Test Stop Level Behavior**:
   ```bash
   # Set stop level to 3
   aws s3api put-bucket-tagging \
     --bucket test-bucket \
     --tagging 'TagSet=[
       {Key=AllowInvalidationEvents,Value=true},
       {Key=invalidator:SiblingDirectoryConsolidationThreshold,Value=8},
       {Key=invalidator:ConsolidationStopLevel,Value=3}
     ]'
   
   # Upload files at depth 3 (should not consolidate)
   aws s3 cp file1.html s3://test-bucket/prod/public/docs/api/file1.html
   aws s3 cp file2.html s3://test-bucket/prod/public/docs/api/file2.html
   
   # Check that individual files are invalidated, not /prod/public/docs/api/*
   ```

## Best Practices

### Configuration Management

1. **Use CloudFormation Parameters for System-Wide Defaults**:
   - Set reasonable defaults that work for most buckets
   - Document parameter choices in deployment guides
   - Use consistent values across environments

2. **Use Bucket Tags for Exceptions**:
   - Only override defaults when necessary
   - Document why specific buckets need different settings

3. **Monitor Configuration Usage**:
   - Set up CloudWatch dashboards for configuration metrics
   - Alert on frequent tag validation warnings
   - Review configuration effectiveness regularly

### Troubleshooting Workflow

1. **Identify the Issue**:
   - Check recent changes to bucket tags or CloudFormation parameters
   - Review error logs and warning messages
   - Compare expected vs. actual consolidation behavior

2. **Gather Diagnostic Information**:
   - Export relevant CloudWatch logs
   - Check current configuration values
   - Verify IAM permissions

3. **Test in Isolation**:
   - Use test bucket with known configuration
   - Upload minimal test files
   - Monitor logs for expected behavior

4. **Apply Fix and Verify**:
   - Make configuration changes
   - Wait for next processing cycle
   - Verify fix in logs and behavior

### Monitoring and Alerting

1. **Key Metrics to Monitor**:
   - Configuration tag validation error rate
   - Stop level prevention frequency
   - Consolidation effectiveness (paths before/after)
   - Processing time impact of configuration features

2. **Recommended Alarms**:
   - High rate of tag validation warnings
   - Unexpected consolidation behavior patterns
   - Configuration reading failures

3. **Regular Reviews**:
   - Monthly review of bucket-specific configurations
   - Quarterly review of system-wide defaults
   - Annual review of consolidation effectiveness

## Support

For additional support:

1. **Check CloudWatch Logs**: Most issues are logged with detailed error messages
2. **Review Configuration**: Verify all settings match intended behavior
3. **Test in Isolation**: Use test buckets to reproduce issues
4. **Contact Platform Team**: Provide logs and configuration details

## Related Documentation

- [Main README](README.md) - Complete system documentation
- [Requirements Document](.kiro/specs/dynamic-bucket-consolidation-config/requirements.md) - Feature requirements
- [Design Document](.kiro/specs/dynamic-bucket-consolidation-config/design.md) - Technical design
- [AWS S3 Bucket Tagging Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-tagging.html)
- [AWS CloudFormation Parameters Documentation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html)