# Deployment Guide - Enhanced Multi-Bucket CloudFront Invalidation Service

This guide provides step-by-step instructions for deploying the enhanced Multi-Bucket CloudFront Invalidation Service with dynamic bucket consolidation configuration capabilities.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Deployment Steps](#deployment-steps)
- [Configuration](#configuration)
- [Validation](#validation)
- [Migration from Previous Version](#migration-from-previous-version)
- [Rollback Procedures](#rollback-procedures)

## Overview

The enhanced system includes the following new capabilities:

- **Dynamic Configuration**: Per-bucket consolidation settings via S3 bucket tags
- **Consolidation Stop Level**: Control consolidation depth to prevent over-consolidation
- **CloudFormation Parameters**: System-wide default configuration values
- **Enhanced Logging**: Comprehensive configuration decision logging

### New Features

1. **Bucket Tags for Configuration**:
   - `invalidator:DirectoryConsolidationThreshold` (1-1000)
   - `invalidator:ConsolidationStopLevel` (0-1000)

2. **CloudFormation Parameters**:
   - `DirectoryConsolidationThreshold` (default: 3)
   - `ConsolidationStopLevel` (default: 1)
   - `AggregationWindowSeconds` (default: 300)

3. **Backward Compatibility**: Existing deployments continue to work without changes

## Prerequisites

### Required Tools

- AWS CLI v2.0 or later
- AWS SAM CLI v1.50 or later
- Python 3.9 or later
- Git

### Required Permissions

Your AWS credentials must have permissions for:

- CloudFormation stack operations
- Lambda function deployment
- IAM role creation and management
- S3 bucket operations
- SQS queue operations
- DynamoDB table operations
- EventBridge scheduler operations
- CloudWatch logs and alarms

### Environment Setup

```bash
# Verify AWS CLI configuration
aws sts get-caller-identity

# Verify SAM CLI installation
sam --version

# Clone repository
git clone <repository-url>
cd application-infrastructure
```

## Deployment Steps

### Step 1: Review Configuration Options

Before deployment, decide on your configuration strategy:

#### Option A: Use Default Configuration
- DirectoryConsolidationThreshold: 3
- ConsolidationStopLevel: 1
- No additional parameters needed

#### Option B: Custom System-Wide Configuration
- Set CloudFormation parameters for your environment
- All buckets use these defaults unless overridden

#### Option C: Mixed Configuration
- Set reasonable CloudFormation defaults
- Use bucket tags for specific overrides

### Step 2: Prepare Deployment Parameters

Create a parameter file for your environment:

**parameters-test.json**:
```json
[
  {
    "ParameterKey": "DeployEnvironment",
    "ParameterValue": "TEST"
  },
  {
    "ParameterKey": "Prefix",
    "ParameterValue": "atlantis"
  },
  {
    "ParameterKey": "ProjectId",
    "ParameterValue": "cloudfront-invalidation"
  },
  {
    "ParameterKey": "StageId",
    "ParameterValue": "test"
  },
  {
    "ParameterKey": "DirectoryConsolidationThreshold",
    "ParameterValue": "3"
  },
  {
    "ParameterKey": "ConsolidationStopLevel",
    "ParameterValue": "1"
  },
  {
    "ParameterKey": "AggregationWindowSeconds",
    "ParameterValue": "300"
  }
]
```

**parameters-prod.json**:
```json
[
  {
    "ParameterKey": "DeployEnvironment",
    "ParameterValue": "PROD"
  },
  {
    "ParameterKey": "Prefix",
    "ParameterValue": "atlantis"
  },
  {
    "ParameterKey": "ProjectId",
    "ParameterValue": "cloudfront-invalidation"
  },
  {
    "ParameterKey": "StageId",
    "ParameterValue": "prod"
  },
  {
    "ParameterKey": "DirectoryConsolidationThreshold",
    "ParameterValue": "5"
  },
  {
    "ParameterKey": "ConsolidationStopLevel",
    "ParameterValue": "2"
  },
  {
    "ParameterKey": "AggregationWindowSeconds",
    "ParameterValue": "180"
  },
  {
    "ParameterKey": "AlarmNotificationEmail",
    "ParameterValue": "ops@example.com"
  },
  {
    "ParameterKey": "FunctionGradualDeploymentType",
    "ParameterValue": "Linear10PercentEvery1Minute"
  }
]
```

### Step 3: Build and Deploy

#### Deploy to TEST Environment

```bash
# Build the application
sam build

# Deploy to TEST
sam deploy \
  --stack-name atlantis-cloudfront-invalidation-test \
  --parameter-overrides file://parameters-test.json \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

#### Deploy to PROD Environment

```bash
# Deploy to PROD with gradual deployment
sam deploy \
  --stack-name atlantis-cloudfront-invalidation-prod \
  --parameter-overrides file://parameters-prod.json \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

### Step 4: Configure S3 Bucket Notifications

After successful deployment, configure your S3 buckets to send events to the Ingestor Lambda:

```bash
# Get the Ingestor Lambda ARN from CloudFormation outputs
INGESTOR_ARN=$(aws cloudformation describe-stacks \
  --stack-name atlantis-cloudfront-invalidation-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`IngestorLambdaArn`].OutputValue' \
  --output text)

echo "Ingestor Lambda ARN: $INGESTOR_ARN"

# Configure S3 bucket notification
aws s3api put-bucket-notification-configuration \
  --bucket your-bucket-name \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [{
      "LambdaFunctionArn": "'$INGESTOR_ARN'",
      "Events": ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"],
      "Filter": {
        "Key": {
          "FilterRules": [{
            "Name": "prefix",
            "Value": "prod/public/"
          }]
        }
      }
    }]
  }'
```

## Configuration

### System-Wide Configuration (CloudFormation Parameters)

These parameters set default values for all buckets:

```bash
# Update stack with new configuration
sam deploy \
  --stack-name atlantis-cloudfront-invalidation-prod \
  --parameter-overrides \
    DirectoryConsolidationThreshold=7 \
    ConsolidationStopLevel=3 \
    AggregationWindowSeconds=240 \
  --capabilities CAPABILITY_IAM
```

### Per-Bucket Configuration (S3 Bucket Tags)

Configure specific buckets with custom settings:

#### Basic Configuration (Required)
```bash
aws s3api put-bucket-tagging \
  --bucket your-bucket-name \
  --tagging 'TagSet=[
    {Key=AllowInvalidationEvents,Value=true}
  ]'
```

#### Advanced Configuration (Optional Overrides)
```bash
aws s3api put-bucket-tagging \
  --bucket your-bucket-name \
  --tagging 'TagSet=[
    {Key=AllowInvalidationEvents,Value=true},
    {Key=invalidator:DirectoryConsolidationThreshold,Value=10},
    {Key=invalidator:ConsolidationStopLevel,Value=0}
  ]'
```

#### Configuration Examples

**High-Traffic Bucket (Aggressive Consolidation)**:
```bash
# Consolidate at 2 files, allow root consolidation
aws s3api put-bucket-tagging \
  --bucket high-traffic-bucket \
  --tagging 'TagSet=[
    {Key=AllowInvalidationEvents,Value=true},
    {Key=invalidator:DirectoryConsolidationThreshold,Value=2},
    {Key=invalidator:ConsolidationStopLevel,Value=0}
  ]'
```

**Documentation Bucket (Conservative Consolidation)**:
```bash
# Consolidate at 20 files, prevent deep consolidation
aws s3api put-bucket-tagging \
  --bucket docs-bucket \
  --tagging 'TagSet=[
    {Key=AllowInvalidationEvents,Value=true},
    {Key=invalidator:DirectoryConsolidationThreshold,Value=20},
    {Key=invalidator:ConsolidationStopLevel,Value=4}
  ]'
```

**API Assets Bucket (Minimal Consolidation)**:
```bash
# High threshold, prevent most consolidation
aws s3api put-bucket-tagging \
  --bucket api-assets-bucket \
  --tagging 'TagSet=[
    {Key=AllowInvalidationEvents,Value=true},
    {Key=invalidator:DirectoryConsolidationThreshold,Value=100},
    {Key=invalidator:ConsolidationStopLevel,Value=5}
  ]'
```

### CloudFront Distribution Configuration

Ensure your CloudFront distributions have the required tags:

```bash
aws cloudfront tag-resource \
  --resource arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE \
  --tags 'Items=[
    {Key=AllowInvalidationEvents,Value=true},
    {Key=atlantis:ApplicationDeploymentId,Value=your-bucket-name-prod}
  ]'
```

## Validation

### Step 1: Verify Deployment

```bash
# Check CloudFormation stack status
aws cloudformation describe-stacks \
  --stack-name atlantis-cloudfront-invalidation-prod \
  --query 'Stacks[0].StackStatus'

# Verify Lambda functions are deployed
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `cloudfront-invalidation`)].{Name:FunctionName,Runtime:Runtime,LastModified:LastModified}'
```

### Step 2: Verify Configuration

```bash
# Check Lambda environment variables
aws lambda get-function-configuration \
  --function-name atlantis-cloudfront-invalidation-prod-processor \
  --query 'Environment.Variables.{DirectoryThreshold:DIRECTORY_CONSOLIDATION_THRESHOLD,StopLevel:CONSOLIDATION_STOP_LEVEL,WindowSeconds:AGGREGATION_WINDOW_SECONDS}'

# Verify bucket tags
aws s3api get-bucket-tagging --bucket your-bucket-name
```

### Step 3: Test Functionality

```bash
# Upload test file
aws s3 cp test.html s3://your-bucket-name/prod/public/test.html

# Monitor Ingestor Lambda logs
aws logs tail /aws/lambda/atlantis-cloudfront-invalidation-prod-ingestor --follow

# Wait 5+ minutes, then monitor Processor Lambda logs
aws logs tail /aws/lambda/atlantis-cloudfront-invalidation-prod-processor --follow
```

### Step 4: Verify Configuration Usage

Check logs for configuration decisions:

```bash
# Query for configuration resolution logs
aws logs start-query \
  --log-group-name /aws/lambda/atlantis-cloudfront-invalidation-prod-processor \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, bucketName, directoryThreshold, stopLevel, source | filter @message like /effective configuration/ | sort @timestamp desc'
```

## Migration from Previous Version

### Backward Compatibility

The enhanced system is fully backward compatible:

- Existing buckets without new tags continue to work
- Default behavior matches previous version (threshold=3, stop_level=1)
- No changes required to existing S3 event configurations

### Migration Steps

1. **Deploy Enhanced System**:
   ```bash
   # Deploy with default parameters (maintains existing behavior)
   sam deploy \
     --stack-name atlantis-cloudfront-invalidation-prod \
     --parameter-overrides \
       DirectoryConsolidationThreshold=3 \
       ConsolidationStopLevel=1 \
     --capabilities CAPABILITY_IAM
   ```

2. **Verify Existing Functionality**:
   - Test with existing buckets
   - Verify consolidation behavior unchanged
   - Check logs for successful processing

3. **Gradually Add Configuration**:
   - Start with test buckets
   - Add configuration tags to specific buckets
   - Monitor behavior and adjust as needed

4. **Optimize System-Wide Defaults**:
   - Based on operational experience
   - Update CloudFormation parameters
   - Document configuration decisions

### Migration Validation

```bash
# Compare consolidation behavior before/after
# Upload same test files and compare invalidation requests

# Before migration (save output)
aws cloudfront list-invalidations --distribution-id EDFDVBD6EXAMPLE

# After migration (compare output)
aws cloudfront list-invalidations --distribution-id EDFDVBD6EXAMPLE
```

## Rollback Procedures

### Emergency Rollback

If issues occur after deployment:

1. **Immediate Rollback**:
   ```bash
   # Rollback CloudFormation stack to previous version
   aws cloudformation cancel-update-stack \
     --stack-name atlantis-cloudfront-invalidation-prod
   
   # Or rollback to specific version
   aws cloudformation update-stack \
     --stack-name atlantis-cloudfront-invalidation-prod \
     --use-previous-template \
     --parameters UsePreviousValue=true
   ```

2. **Partial Rollback (Configuration Only)**:
   ```bash
   # Reset to previous configuration values
   sam deploy \
     --stack-name atlantis-cloudfront-invalidation-prod \
     --parameter-overrides \
       DirectoryConsolidationThreshold=3 \
       ConsolidationStopLevel=1 \
     --capabilities CAPABILITY_IAM
   ```

### Rollback Validation

```bash
# Verify rollback success
aws cloudformation describe-stacks \
  --stack-name atlantis-cloudfront-invalidation-prod \
  --query 'Stacks[0].StackStatus'

# Test functionality
aws s3 cp test.html s3://your-bucket-name/prod/public/rollback-test.html

# Monitor logs for expected behavior
aws logs tail /aws/lambda/atlantis-cloudfront-invalidation-prod-processor --follow
```

## Troubleshooting

### Common Deployment Issues

1. **Parameter Validation Errors**:
   - Check parameter value ranges
   - Verify parameter file format
   - Review CloudFormation template constraints

2. **IAM Permission Issues**:
   - Verify deployment role has required permissions
   - Check service role policies
   - Review resource-based policies

3. **Resource Naming Conflicts**:
   - Ensure unique stack names
   - Check for existing resources with same names
   - Verify prefix and project ID combinations

### Post-Deployment Issues

1. **Configuration Not Applied**:
   - Check Lambda environment variables
   - Verify CloudFormation parameter values
   - Review bucket tag formatting

2. **Functionality Issues**:
   - Check S3 event configuration
   - Verify bucket and distribution tags
   - Review IAM permissions for Lambda functions

For detailed troubleshooting, see [Configuration Troubleshooting Guide](CONFIGURATION_TROUBLESHOOTING.md).

## Best Practices

### Deployment

1. **Test in Non-Production First**: Always deploy to TEST environment before PROD
2. **Use Parameter Files**: Maintain consistent configuration across deployments
3. **Monitor Deployments**: Watch CloudFormation events and Lambda function updates
4. **Validate After Deployment**: Test functionality before declaring success

### Configuration Management

1. **Document Configuration Decisions**: Record why specific settings were chosen
2. **Use Consistent Naming**: Follow established patterns for resource names
3. **Monitor Configuration Usage**: Track which buckets use custom settings
4. **Regular Reviews**: Periodically review and optimize configuration

### Operations

1. **Monitor Key Metrics**: Track consolidation effectiveness and error rates
2. **Set Up Alerts**: Configure alarms for configuration issues
3. **Maintain Documentation**: Keep deployment and configuration guides current
4. **Plan for Growth**: Consider configuration needs as system scales

## Support

For deployment support:

1. **Check CloudFormation Events**: Review stack events for deployment issues
2. **Review Lambda Logs**: Check function logs for runtime issues
3. **Validate Configuration**: Verify all settings match intended behavior
4. **Contact Platform Team**: Provide deployment logs and configuration details

## Related Documentation

- [Main README](README.md) - Complete system documentation
- [Configuration Troubleshooting Guide](CONFIGURATION_TROUBLESHOOTING.md) - Detailed troubleshooting
- [Requirements Document](.kiro/specs/dynamic-bucket-consolidation-config/requirements.md) - Feature requirements
- [Design Document](.kiro/specs/dynamic-bucket-consolidation-config/design.md) - Technical design