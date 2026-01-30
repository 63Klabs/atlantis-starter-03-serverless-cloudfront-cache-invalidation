# Multi-Bucket CloudFront Invalidation Service

An event-driven, serverless application that automatically invalidates CloudFront cache entries when objects are updated in S3 buckets. The system is designed to be decoupled from specific buckets and distributions, using tag-based discovery and validation to support multiple applications within the 63Klabs Atlantis Platform Templates and Scripts framework.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [Architecture Components](#architecture-components)
- [Aggregation Window Mechanism](#aggregation-window-mechanism)
- [Path Consolidation Algorithm](#path-consolidation-algorithm)
- [Required Tags](#required-tags)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
- [Testing](#testing)
- [Cost Optimization](#cost-optimization)

## Architecture Overview

The system consists of two primary Lambda functions that work together to process S3 events and create CloudFront invalidations:

```
╔══════════════════╗
║ - [ External ] - ║═╗
║  S3 Bucket       ║ ║
║  (Multiple)      ║ ║
╚╦═════════════════╝ ║
 ╚═══════════════════╝
       │ S3 Event Trigger
       │ (PUT/POST/COPY/DELETE)
       ▼
┌─────────────────────┐
│  Ingestor Lambda    │
│  - Filter events    │
│  - Extract metadata │
│  - Queue valid msgs │
│  - Track window     │
└──────┬──────────────┘
       │
       ├─────────────────┬─────────────────┐
       │                 │ Check window    │ Create schedule
       ▼                 ▼                 ▼ 
┌─────────────┐   ┌──────────────┐   ┌──────────────────┐
│  SQS Queue  │   │  DynamoDB    │   │ EventBridge      │
│  (Standard) │   │  (Tracking)  │   │ Scheduler        │
└─────────────┘   └──────────────┘   │ (One-time, +5min)│
       ▲             ▲               └──────┬───────────┘ 
       │             | Close Window         |
       │ Poll Queue  |                      │ After 5 minutes
       |             |  ┌───────────────────┘
       |             |  ▼
┌────────────────────────────────┐
│  Processor Lambda              │
│  - Batch read from SQS         │      ┌─────────────┐
│  - Group events by bucket      │─────►│  SQS DLQ    │
│  - Read bucket tags            │      │  (Failures) │
│  - Consolidate paths           │      └─────────────┘
│  - Resolve distributions       │
│  - Submit invalidations        │
└────────────┬───────────────────┘
             │
             ▼
     ╔══════════════════╗
     ║ - [ External ] - ║═╗
     ║  CloudFront      ║ ║
     ║  Distributions   ║ ║
     ║  (Multiple)      ║ ║
     ╚╦═════════════════╝ ║
      ╚═══════════════════╝
```

## Key Features

- **Decoupled Architecture**: Single stack supports any number of S3 buckets and CloudFront distributions
- **Tag-Driven Discovery**: Uses AWS resource tags for permission validation and resource discovery
- **Event Aggregation**: Collects events over a 5-minute (configurable) window to batch process invalidations
- **Dynamic Path Consolidation**: Reduces invalidation paths with configurable thresholds and stop levels
- **Per-Bucket Configuration**: Override global settings using S3 bucket tags for customized behavior
- **Consolidation Stop Level**: Control consolidation depth to prevent over-consolidation
- **CloudFormation Parameters**: System-wide default configuration with environment-specific values
- **Comprehensive Logging**: Detailed configuration decision logging for troubleshooting and auditing
- **Secure**: Implements least-privilege IAM policies with tag-based conditions
- **Cost-Effective**: Uses on-demand scheduling instead of constant cron jobs
- **Production-Ready**: Includes monitoring, alarms, and gradual deployment for PROD environments

## Architecture Components

### 1. Ingestor Lambda

**Purpose**: Receives S3 events, filters them, queues valid events, and manages aggregation window scheduling.

**Responsibilities**:
- Parse S3 event notifications
- Filter events based on application-wide origin path pattern
- Filter events based on StageId (production environments: p*, s*, b*)
- Send valid events to SQS queue
- Track aggregation windows in DynamoDB
- Create EventBridge one-time schedules for processing (schedule runs then self-deletes)

### 2. Processor Lambda

**Purpose**: Processes queued events, validates permissions, consolidates paths, and submits CloudFront invalidations.

**Responsibilities**:
- Retrieve messages from SQS in batches
- Group events by bucket and origin path
- Validate S3 bucket tags (AllowInvalidationEvents=true)
- Discover CloudFront distributions matching bucket origins
- Validate CloudFront distribution tags
- Consolidate invalidation paths using threshold algorithm
- Submit CreateInvalidation requests to CloudFront
- Delete processed messages from SQS
- Close aggregation window in DynamoDB

### 3. SQS Event Queue

**Type**: Standard Queue (higher throughput, no ordering guarantee)

**Configuration**:
- Visibility Timeout: 300 seconds
- Message Retention: 4 days
- Long Polling: 20 seconds
- Dead Letter Queue: Enabled after 3 receives

### 4. DynamoDB Tracking Table

**Purpose**: Tracks active aggregation windows to prevent duplicate scheduling.

**Schema**:
- Partition Key: `windowId` (String) - Fixed value "current"
- Attributes:
  - `scheduleArn` - EventBridge Schedule ARN
  - `windowStartTime` - Unix timestamp
  - `windowEndTime` - Unix timestamp (TTL)
  - `status` - "active" or "closed"

### 5. EventBridge Scheduler

**Purpose**: Creates one-time schedules to invoke Processor Lambda after aggregation window.

**Configuration**:
- Schedule Expression: `at(YYYY-MM-DDTHH:MM:SS)` (one-time)
- Target: Processor Lambda ARN
- Auto-delete: After completion

## Aggregation Window Mechanism

The aggregation window mechanism batches S3 events over a 5-minute period to process them efficiently:

### How It Works

1. **First Event**: When the Ingestor Lambda receives the first S3 event:
   - Checks DynamoDB for an active aggregation window
   - If no active window exists, creates a new window record
   - Creates an EventBridge one-time schedule for 5 minutes in the future
   - Sends the event to SQS queue

2. **Subsequent Events**: When additional events arrive during the window:
   - Checks DynamoDB and finds an active window
   - Does NOT create a new schedule
   - Sends the event to SQS queue

3. **Window Processing**: After 5 minutes:
   - EventBridge Scheduler invokes the Processor Lambda
   - Processor retrieves ALL messages from SQS queue
   - Processes all events in batch
   - Closes the aggregation window in DynamoDB

4. **Next Window**: After the window closes:
   - The next S3 event will create a new aggregation window
   - The cycle repeats

> Note: Often multiple S3 events may come in at the same time creating a race condition where multiple schedules will be created (up to around 4 or 5). This does not affect processing.

### Benefits

- **Cost Savings**: No constant cron job running
- **Efficient Batching**: Multiple events processed together
- **Reduced API Calls**: Path consolidation across all events in window
- **Scalable**: Handles bursts of S3 events gracefully

## Path Consolidation Algorithm

The path consolidation algorithm reduces the number of invalidation paths by replacing multiple individual paths with directory-level wildcards. The system supports both global defaults (set via CloudFormation parameters) and per-bucket overrides (set via S3 bucket tags).

### Dynamic Configuration

#### Global Configuration (CloudFormation Parameters)

Set system-wide defaults for all buckets:

- **DirectoryConsolidationThreshold**: Number of files that triggers directory consolidation (default: 3, range: 1-1000)
- **SiblingDirectoryConsolidationThreshold**: Number of sibling directories that triggers consolidation to parent wildcard (default: 10, range: 1-1000)
- **ConsolidationStopLevel**: Directory depth from root where consolidation stops (default: 1, range: 0-20)
- **AggregationWindowSeconds**: Event aggregation window duration (default: 300, range: 60-900)
- **OriginPathPattern**: Pattern for expected paths from S3. Default: `/{stageId}/public` where `{stageId}` is a placeholder for a variable stage. Use `/` to turn off ingestion filtering and use root or allow buckets to specify their own pattern.

#### Per-Bucket Configuration (S3 Bucket Tags)

Override global settings for specific buckets using these tags:

```
Key: invalidator:DirectoryConsolidationThreshold
Value: 5  (range: 1-1000)

Key: invalidator:SiblingDirectoryConsolidationThreshold
Value: 15  (range: 1-1000)

Key: invalidator:ConsolidationStopLevel  
Value: 2  (range: 0-20)

Key: invalidator:OriginPathPattern
Value: /@stageId@/public (examples: / , /@stageId@ , /web)
```

> Note: Since AWS resource tags do not accept `{}` characters in values, `@` is used to surround the `stageId` placeholder instead. This is only for tags. Use `{stageId}` for all other patterns.

To configure, refer to: [Deployment Guide: Configuration](./DEPLOYMENT_GUIDE.md#configuration)

### Consolidation Rules

#### 1. Index and Default File Consolidation

When an event is received for a file matching `*/index.*` or `*/default.*`, the system automatically creates a directory-level invalidation (unless prevented by stop level):

```
Input:  /prod/public/docs/index.html
Output: /prod/public/docs/*
```

#### 2. Directory Threshold Consolidation

When the number of files in a directory exceeds the threshold (global default or bucket-specific), consolidate to directory level:

```
# With DirectoryConsolidationThreshold = 3
Input:  /prod/public/images/logo.png
        /prod/public/images/banner.jpg
        /prod/public/images/icon.svg
        /prod/public/images/background.png
Output: /prod/public/images/*

# With DirectoryConsolidationThreshold = 3 but not threshold not met
Input:  /prod/public/images/logo.png
        /prod/public/images/banner.jpg
Output: /prod/public/images/logo.png
        /prod/public/images/banner.jpg

# With bucket tag DirectoryConsolidationThreshold = 5
Input:  5+ files in /prod/public/css/
Output: /prod/public/css/*
```

#### 3. Consolidation Stop Level

The stop level prevents consolidation at or above a specified directory depth from the root:

(The root refers to the Origin Path used by CloudFront. It is in the `public/` directory of the S3 object path: `StageId/public/*ROOT*)

```
# ConsolidationStopLevel = 0: Consolidate everything to root
Input:  Any paths
Output: /*

# ConsolidationStopLevel = 1 (default): Allow normal consolidation
Input:  /prod/public/dir1/*, /prod/public/dir2/*
Output (if threshold not met): /prod/public/dir1/*, /prod/public/dir2/*
Output (if threshold met): /prod/public/*

# ConsolidationStopLevel = 2: Prevent consolidation at depth 2
Input:  /prod/public/dir1/a/*, /prod/public/dir1/b/*
Output: /prod/public/dir1/a/*, /prod/public/dir1/b/* (no consolidation to /prod/public/dir1/*)

# ConsolidationStopLevel = 3: Prevent consolidation at depth 3
Input:  /prod/public/dir1/sub/file1.html, /prod/public/dir1/sub/file2.html
Output: Individual files (no consolidation to /prod/public/dir1/sub/*)
```

#### 4. Sibling Directory Consolidation

When the number of sibling directories exceeds the threshold (global default or bucket-specific), consolidate to parent (unless prevented by stop level):

```
# With SiblingDirectoryConsolidationThreshold = 10 (default)
Input:  /prod/public/dir1/*
        /prod/public/dir2/*
        /prod/public/dir3/*
        ... (11 directories)
Output: /prod/public/* (if stop level allows)

# With bucket tag SiblingDirectoryConsolidationThreshold = 5
Input:  6+ sibling directories at /prod/public/
Output: /prod/public/* (if stop level allows)
```

#### 5. Root Consolidation

When consolidation reaches the origin path root, uses `/*`:

```
Input:  Multiple directories at root level
Output: /prod/public/*
```

#### 6. Request Splitting

If consolidated paths exceed the limit for a single distribution (default 1000), split into multiple invalidation requests:

```
Input:  1500 paths
Output: Request 1: 1000 paths
        Request 2: 500 paths
```

### Configuration Priority

The system uses the following priority order for configuration values:

1. **Bucket Tags** (highest priority): `invalidator:DirectoryConsolidationThreshold`, `invalidator:SiblingDirectoryConsolidationThreshold`, `invalidator:ConsolidationStopLevel`, `invalidator:OriginPathPattern`
2. **CloudFormation Parameters**: `DirectoryConsolidationThreshold`, `SiblingDirectoryConsolidationThreshold`, `ConsolidationStopLevel`
3. **Hardcoded Defaults** (fallback): directory_threshold=3, sibling_threshold=10, stop_level=1

### Example Consolidation Flows

#### Standard Configuration (threshold=3, stop_level=1)

```
Original Events:
- /prod/public/css/main.css
- /prod/public/css/theme.css
- /prod/public/css/responsive.css
- /prod/public/css/print.css
- /prod/public/js/app.js
- /prod/public/js/vendor.js
- /prod/public/images/index.html

After Consolidation:
- /prod/public/css/*        (4 files → directory)
- /prod/public/js/app.js    (only 2 files, no consolidation)
- /prod/public/js/vendor.js
- /prod/public/images/*     (index.html → directory)
```

#### High Stop Level Configuration (threshold=3, stop_level=3)

```
Original Events:
- /prod/public/docs/api/file1.html
- /prod/public/docs/api/file2.html
- /prod/public/docs/api/file3.html
- /prod/public/docs/api/file4.html

After Consolidation:
- /prod/public/docs/api/file1.html  (stop level prevents consolidation)
- /prod/public/docs/api/file2.html
- /prod/public/docs/api/file3.html
- /prod/public/docs/api/file4.html
```

#### Root Consolidation (stop_level=0)

```
Original Events:
- /prod/public/css/main.css
- /prod/public/js/app.js
- /prod/public/images/logo.png

After Consolidation:
- /prod/public/*  (all paths consolidated to root)
```

## Required Tags

### S3 Bucket Tags

#### Required Tags

For an S3 bucket to allow invalidations, it MUST have the following tag:

```
Key: AllowInvalidationEvents
Value: true
```

This tag is automatically added to buckets created by the Atlantis Template for stacks that provision S3 buckets using OAC (Object Access Control) for use with CloudFront distributions when the Invalidator Service ARN is provided as a parameter during CloudFormation stack deployment.

Refer to: [Deployment Guide: Configuration](./DEPLOYMENT_GUIDE.md#deployment-steps)

#### Optional Configuration Tags

Buckets can override global consolidation settings using these optional tags:

```
Key: invalidator:DirectoryConsolidationThreshold
Value: 1-1000 (number of files that triggers directory consolidation)

Key: invalidator:SiblingDirectoryConsolidationThreshold
Value: 1-1000 (number of sibling directories that triggers consolidation to parent wildcard)

Key: invalidator:ConsolidationStopLevel
Value: 0-20 (directory depth from root where consolidation stops)

Key: invalidator:OriginPathPattern
Value: /@stageId@/public (origin path to match and filter against)
```

**Configuration Tag Behavior**:
- **DirectoryConsolidationThreshold**: Controls when files in a directory are consolidated to `directory/*`
  - Lower values = more aggressive consolidation
  - Higher values = less consolidation, more individual file invalidations
  - Range: 1-1000, defaults to CloudFormation parameter value
- **SiblingDirectoryConsolidationThreshold**: Controls when sibling directories are consolidated to parent wildcard
  - Lower values = more aggressive sibling consolidation
  - Higher values = less sibling consolidation, more individual directory wildcards
  - Range: 1-1000, defaults to CloudFormation parameter value
- **ConsolidationStopLevel**: Controls the maximum depth where consolidation can occur
  - 0 = consolidate everything to root `/*`
  - 1 = allow normal consolidation (default)
  - 2+ = prevent consolidation at that depth or shallower
  - Range: 0-20, defaults to CloudFormation parameter value

Add tags during S3 stack deployment when prompted to add additional tags:
- `invalidator:DirectoryConsolidationThreshold=5`
- `invalidator:SiblingDirectoryConsolidationThreshold=15`
- `invalidator:ConsolidationStopLevel=2`

**Tag Validation**:
- Invalid tag values (non-numeric, out of range) are logged and ignored
- System falls back to CloudFormation parameter defaults for invalid tags
- Missing configuration tags use CloudFormation parameter defaults

### CloudFront Distribution Tags

For a CloudFront distribution to receive invalidations, it MUST have BOTH tags:

```
Key: AllowInvalidationEvents
Value: true

Key: atlantis:ApplicationDeploymentId
Value: <bucket-atlantis:Application>-<StageId>
```

**Example**:
```
AllowInvalidationEvents: true
atlantis:ApplicationDeploymentId: acme-static-assets-prod
```

**How to Add**:

The `atlantis:ApplicationDeploymentId` tags is automatically added when the CloudFormation stack provisioning the distribution is deployed.

However, when prompted to add new tags during configuration be sure to add the `AllowInvalidationEvents` tag.

```
AllowInvalidationEvents=true
```

Refer to: [Deployment Guide: Configuration](./DEPLOYMENT_GUIDE.md#deployment-steps)

### Tag Validation Flow

1. **Bucket Validation**: Processor checks S3 bucket tags before processing events
2. **Distribution Discovery**: Processor finds distributions matching bucket origin
3. **Distribution Validation**: Processor checks distribution tags before submitting invalidation
4. **Skip on Failure**: If tags are missing or incorrect, processing for that bucket is skipped and logged

## Configuration

### Environment Variables

#### Ingestor Lambda
- `DEPLOY_ENVIRONMENT`: Deployment environment (PROD, TEST, or DEV)
- `LOG_LEVEL`: INFO (PROD) or DEBUG (TEST/DEV)
- `LAMBDA_TIMEOUT_IN_SEC`: Lambda timeout in seconds (matches IngestorTimeoutInSeconds parameter)
- `AWS_LAMBDA_LOG_LEVEL`: INFO (PROD) or DEBUG (TEST/DEV)
- `AWS_LAMBDA_LOG_FORMAT`: json
- `PREFIX`: Resource naming prefix
- `PROJECT_ID`: Project identifier
- `STAGE_ID`: Stage identifier
- `QUEUE_URL`: SQS queue URL for event messages
- `TRACKING_TABLE`: DynamoDB table name for window tracking
- `PROCESSOR_FUNCTION_ARN`: ARN of Processor Lambda
- `SCHEDULER_ROLE_ARN`: ARN of EventBridge Scheduler execution role
- `AGGREGATION_WINDOW_SECONDS`: Window duration (default: 300)
- `ORIGIN_PATH_PATTERN`: Pattern for expected paths from S3 (default: /{stageId}/public)

#### Processor Lambda
- `DEPLOY_ENVIRONMENT`: Deployment environment (PROD, TEST, or DEV)
- `LOG_LEVEL`: INFO (PROD) or DEBUG (TEST/DEV)
- `LAMBDA_TIMEOUT_IN_SEC`: Lambda timeout in seconds (matches ProcessorTimeoutInSeconds parameter)
- `AWS_LAMBDA_LOG_LEVEL`: INFO (PROD) or DEBUG (TEST/DEV)
- `AWS_LAMBDA_LOG_FORMAT`: json
- `PREFIX`: Resource naming prefix
- `PROJECT_ID`: Project identifier
- `STAGE_ID`: Stage identifier
- `QUEUE_URL`: SQS queue URL for event messages
- `TRACKING_TABLE`: DynamoDB table name for window tracking
- `MAX_BATCH_SIZE`: SQS batch size (default: 10)
- `MAX_PATHS_PER_INVALIDATION`: CloudFront limit (default: 1000)
- `ORIGIN_PATH_PATTERN`: Pattern for expected paths from S3 (default: /{stageId}/public)
- `AGGREGATION_WINDOW_SECONDS`: Event aggregation window duration (default: 300)
- `DIRECTORY_CONSOLIDATION_THRESHOLD`: Default directory consolidation threshold (default: 3)
- `CONSOLIDATION_STOP_LEVEL`: Default consolidation stop level (default: 1)
- `SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD`: Default sibling directory consolidation threshold (default: 10)

### CloudFormation Parameters

#### Application Resource Naming

- `Prefix`: Resource naming prefix (e.g., "acme")
- `ProjectId`: Project identifier
- `StageId`: Stage identifier (prod, test, dev)
- `S3BucketNameOrgPrefix`: S3 bucket naming prefix (e.g., "acmeco")
- `RolePath`: IAM role path
- `PermissionsBoundaryArn`: IAM permissions boundary

#### Deployment Environment

- `DeployEnvironment`: PROD, TEST, or DEV
- `FunctionGradualDeploymentType`: Deployment strategy (PROD only)
- `DeployRole`: CloudFormation service role
- `AlarmNotificationEmail`: Email for CloudWatch Alarms (PROD only)

#### Application Parameters

- `LogRetentionInDaysForPROD`: Log retention for PROD (default: 90)
- `LogRetentionInDaysForDEVTEST`: Log retention for TEST/DEV (default: 7)
- `AggregationWindowSeconds`: Event aggregation window duration (default: 300, range: 60-900)
- `DirectoryConsolidationThreshold`: Default threshold for directory consolidation (default: 3, range: 1-1000)
- `SiblingDirectoryConsolidationThreshold`: Default threshold for sibling directory consolidation (default: 10, range: 1-1000)
- `ConsolidationStopLevel`: Directory depth from root where consolidation stops (default: 1, range: 0-20)
- `MaxPathsPerInvalidation`: Maximum paths per CloudFront invalidation request (default: 1000, range: 1-3000)
- `OriginPathPattern`: Pattern for expected paths from S3 (default: /{stageId}/public)

#### Lambda Function Settings

- `IngestorTimeoutInSeconds`: Ingestor Lambda timeout (default: 10, range: 3-30)
- `IngestorMemoryInMB`: Ingestor Lambda memory (default: 256, range: 128-10240)
- `ProcessorTimeoutInSeconds`: Processor Lambda timeout (default: 300, range: 60-900)
- `ProcessorMemoryInMB`: Processor Lambda memory (default: 512, range: 128-10240)
- `FunctionArchitecture`: Lambda architecture (default: arm64, options: x86_64 or arm64)

## Monitoring and Troubleshooting

### CloudWatch Logs

Both Lambda functions write structured JSON logs to CloudWatch:

**Log Groups**:

- `/aws/lambda/<Prefix>-<ProjectId>-<StageId>-ingestor`
- `/aws/lambda/<Prefix>-<ProjectId>-<StageId>-processor`

**Log Insights Queries**:

Find all filtered events:

```
fields @timestamp, bucketName, objectKey, reason
| filter @message like /filtered/
| sort @timestamp desc
```

Find all invalidation submissions:

```
fields @timestamp, distributionId, invalidationId, pathCount
| filter @message like /invalidation created/
| sort @timestamp desc
```

Find all errors:

```
fields @timestamp, @message
| filter @type = "ERROR"
| sort @timestamp desc
```

Find configuration decisions:

```
fields @timestamp, bucketName, directoryThreshold, stopLevel, source
| filter @message like /effective configuration/
| sort @timestamp desc
```

Find consolidation prevention due to stop level:

```
fields @timestamp, @message, paths
| filter @message like /consolidation prevented.*stop level/
| sort @timestamp desc
```

Find bucket tag validation warnings:

```
fields @timestamp, bucketName, tagKey, tagValue, reason
| filter @message like /invalid.*tag/
| sort @timestamp desc
```

### CloudWatch Alarms (PROD Only)

The system creates the following alarms in PROD:

1. **Ingestor Lambda Errors**: Triggers when error count > 1 in 15 minutes
2. **Processor Lambda Errors**: Triggers when error count > 1 in 15 minutes
3. **Dead Letter Queue Messages**: Triggers when DLQ message count > 0
4. **Processor Lambda Duration**: Triggers when duration > 240 seconds

**Alarm Actions**:
- Send notification to SNS topic
- Email sent to configured address
- Automatic rollback during gradual deployment

### Common Issues and Solutions

#### Issue: Events Not Being Processed

**Symptoms**: S3 events are sent but no invalidations occur

**Troubleshooting**:
1. Check Ingestor Lambda logs for filtering reasons
2. Verify StageId matches pattern (p*, s*, b*)
3. Verify object key matches `/<StageId>/public/*`
4. Check S3 bucket has `AllowInvalidationEvents=true` tag
5. Verify SQS queue has messages

**Solution**: Add required tags or adjust S3 event filter

#### Issue: Invalidations Not Submitted

**Symptoms**: Events are queued but no CloudFront invalidations created

**Troubleshooting**:
1. Check Processor Lambda logs for tag validation failures
2. Verify CloudFront distribution has required tags
3. Verify `atlantis:ApplicationDeploymentId` matches pattern
4. Check IAM permissions for CloudFront CreateInvalidation

**Solution**: Add required distribution tags or fix IAM policy

#### Issue: Messages in Dead Letter Queue

**Symptoms**: DLQ alarm triggers, messages accumulate in DLQ

**Troubleshooting**:
1. Check DLQ messages for error patterns
2. Review Processor Lambda logs for processing failures
3. Check for malformed messages
4. Verify IAM permissions

**Solution**: Fix underlying issue, then manually reprocess DLQ messages

#### Issue: High CloudFront Costs

**Symptoms**: Unexpected CloudFront invalidation charges

**Troubleshooting**:
1. Check number of invalidation requests in CloudWatch
2. Review path consolidation effectiveness
3. Check for excessive S3 events
4. Review consolidation configuration (threshold too high, stop level too high)

**Solution**: Adjust consolidation thresholds or reduce S3 event frequency

#### Issue: Bucket Configuration Tags Not Working

**Symptoms**: Bucket-specific consolidation settings are ignored

**Troubleshooting**:
1. Verify bucket tags are correctly formatted:
   ```bash
   aws s3api get-bucket-tagging --bucket your-bucket-name
   ```
2. Check Processor Lambda logs for tag reading errors
3. Verify tag values are within valid ranges (1-1000 for threshold, 0-1000 for stop level)
4. Check for typos in tag keys (`invalidator:DirectoryConsolidationThreshold`, `invalidator:ConsolidationStopLevel`)

**Solution**: Fix tag formatting or values, redeploy if needed

#### Issue: Consolidation Not Working as Expected

**Symptoms**: Files not being consolidated or over-consolidated

**Troubleshooting**:
1. Check effective configuration in Processor Lambda logs:
   ```
   fields @timestamp, bucketName, effectiveConfig
   | filter @message like /effective configuration/
   ```
2. Verify stop level settings aren't preventing expected consolidation
3. Check directory threshold settings
4. Review path depth calculations in logs

**Solution**: Adjust bucket tags or CloudFormation parameters

#### Issue: Invalid Configuration Values

**Symptoms**: Warning logs about invalid tag values, fallback to defaults

**Troubleshooting**:
1. Check Processor Lambda logs for validation warnings:
   ```
   fields @timestamp, @message
   | filter @message like /invalid.*tag/
   ```
2. Verify tag values are numeric and within valid ranges
3. Check for extra whitespace or special characters in tag values

**Solution**: Update bucket tags with valid values

#### Issue: Configuration Changes Not Taking Effect

**Symptoms**: Updated bucket tags or CloudFormation parameters not reflected in behavior

**Troubleshooting**:
1. For bucket tags: Changes take effect immediately on next processing cycle
2. For CloudFormation parameters: Requires stack update and Lambda restart
3. Check Lambda environment variables match CloudFormation parameters:
   ```bash
   aws lambda get-function-configuration \
     --function-name <processor-function-name> \
     --query 'Environment.Variables'
   ```

**Solution**: Update CloudFormation stack or wait for next processing cycle

### X-Ray Tracing

X-Ray tracing is enabled in PROD and TEST environments for performance analysis:

**Access X-Ray**:
1. Open AWS X-Ray console
2. Select "Service Map" to view component interactions
3. Select "Traces" to view individual request traces
4. Analyze performance bottlenecks

### Metrics to Monitor

**Key Metrics**:
- Ingestor Lambda invocations and errors
- Processor Lambda invocations and duration
- SQS queue message count and age
- DLQ message count
- CloudFront invalidation count
- DynamoDB read/write capacity

**Recommended Dashboards**:
- Lambda performance (invocations, duration, errors)
- SQS queue health (message count, age, DLQ)
- CloudFront invalidation activity
- Cost tracking (Lambda, SQS, CloudFront)

## Testing

### Unit Tests

Run unit tests for individual components:

```bash
cd application-infrastructure
pytest tests/unit/ -v
```

### Property-Based Tests

Run property-based tests using Hypothesis:

```bash
pytest tests/property/ -v
```

### Integration Tests

Run integration tests against real AWS services:

```bash
# Set AWS credentials for TEST environment
export AWS_PROFILE=test

# Run integration tests
pytest tests/integration/ -v
```

### Manual Testing

1. **Upload a file to S3**:
   ```bash
   aws s3 cp test.html s3://your-bucket/prod/public/test.html
   ```

2. **Check Ingestor Lambda logs**:
   ```bash
   aws logs tail /aws/lambda/atlantis-cloudfront-invalidation-prod-ingestor --follow
   ```

3. **Wait 5 minutes for processing**

4. **Check Processor Lambda logs**:
   ```bash
   aws logs tail /aws/lambda/atlantis-cloudfront-invalidation-prod-processor --follow
   ```

5. **Verify invalidation in CloudFront**:
   ```bash
   aws cloudfront list-invalidations --distribution-id EDFDVBD6EXAMPLE
   ```

## Cost Optimization

### Cost Breakdown

**Estimated Costs**:
- CloudFront Invalidations: $0.005 per path (first 1000 free)
- EventBridge Scheduler: $0.01 per invocation
- Lambda, SQS, DynamoDb, and CloudWatch logs

### Cost Optimization Strategies

1. **Path Consolidation**: Reduces CloudFront invalidation costs by minimizing paths
2. **Event Aggregation**: Reduces Lambda invocations by batching events
3. **On-Demand Scheduling**: No constant cron job costs
4. **Short Log Retention**: 7 days in TEST/DEV reduces storage costs
5. **Conditional Alarms**: Alarms only in PROD reduces CloudWatch costs

### Scaling Considerations

The system scales automatically with S3 event volume:
- Ingestor Lambda: Scales with concurrent S3 events
- SQS Queue: Handles bursts of messages
- Processor Lambda: Single concurrency prevents duplicate processing
- DynamoDB: On-demand capacity scales automatically

## Related Documentation

### Project Documentation
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Step-by-step deployment instructions for enhanced system
- [Configuration Troubleshooting Guide](CONFIGURATION_TROUBLESHOOTING.md) - Detailed troubleshooting for configuration issues

### AWS Documentation
- [AWS Serverless Application Model (SAM)](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)
- [CloudFront Invalidation API](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Invalidation.html)
- [EventBridge Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html)
- [S3 Bucket Tagging](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-tagging.html)
- [CloudFormation Parameters](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html)

### Platform Documentation
- [Atlantis Platform Templates and Scripts Documentation](https://github.com/63Klabs/atlantis-cfn-configuration-repo-for-serverless-deployments)
- [Atlantis Platform Templates and Scripts Tutorials](https://github.com/63Klabs/atlantis-tutorials)

## Support

For issues, questions, or contributions:
- Review CloudWatch Logs for error details
- Check DLQ for failed messages
- Review X-Ray traces for performance issues
- Contact platform team for assistance

## License

This project is part of the Atlantis Platform and follows the platform's licensing terms.
