# Multi-Bucket CloudFront Invalidation Service

An event-driven, serverless application that automatically invalidates CloudFront cache entries when objects are updated in S3 buckets. The system is designed to be decoupled from specific buckets and distributions, using tag-based discovery and validation to support multiple applications within the Atlantis Platform framework.

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
┌─────────────┐
│  S3 Bucket  │
│  (Multiple) │
└──────┬──────┘
       │ S3 Event
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
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌─────────────┐   ┌──────────────┐
│  SQS Queue  │   │  DynamoDB    │
│  (Standard) │   │  (Tracking)  │
└──────┬──────┘   └──────┬───────┘
       │                 │
       │                 │ Check window
       │                 │ Create schedule
       │                 ▼
       │          ┌──────────────────┐
       │          │ EventBridge      │
       │          │ Scheduler        │
       │          │ (One-time, +5min)│
       │          └──────┬───────────┘
       │                 │
       │                 │ After 5 minutes
       ▼                 ▼
┌────────────────────────────────┐
│  Processor Lambda              │
│  - Batch read from SQS         │
│  - Validate bucket tags        │
│  - Resolve distributions       │
│  - Validate distribution tags  │
│  - Consolidate paths           │
│  - Submit invalidations        │
└────────────┬───────────────────┘
             │
             ▼
┌─────────────────────┐
│  CloudFront         │
│  Distributions      │
│  (Multiple)         │
└─────────────────────┘

┌─────────────┐
│  SQS DLQ    │
│  (Failures) │
└─────────────┘
```

## Key Features

- **Decoupled Architecture**: Single stack supports any number of S3 buckets and CloudFront distributions
- **Tag-Driven Discovery**: Uses AWS resource tags for permission validation and resource discovery
- **Event Aggregation**: Collects events over a 5-minute window to batch process invalidations
- **Path Consolidation**: Intelligently reduces the number of invalidation paths to minimize API calls
- **Secure**: Implements least-privilege IAM policies with tag-based conditions
- **Cost-Effective**: Uses on-demand scheduling instead of constant cron jobs
- **Production-Ready**: Includes monitoring, alarms, and gradual deployment for PROD environments

## Architecture Components

### 1. Ingestor Lambda

**Purpose**: Receives S3 events, filters them, queues valid events, and manages aggregation window scheduling.

**Responsibilities**:
- Parse S3 event notifications
- Filter events based on StageId (production environments: p*, s*, b*)
- Filter events based on path pattern (`/<StageId>/public/*`)
- Send valid events to SQS queue
- Track aggregation windows in DynamoDB
- Create EventBridge one-time schedules for processing

**Configuration**:
- Timeout: 10 seconds
- Memory: 256 MB
- Concurrency: Unlimited (scales with S3 events)

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

**Configuration**:
- Timeout: 300 seconds (5 minutes)
- Memory: 512 MB
- Concurrency: 1 (prevents duplicate processing)

### 3. SQS Event Queue

**Type**: Standard Queue (higher throughput, no ordering guarantee)

**Configuration**:
- Visibility Timeout: 300 seconds
- Message Retention: 4 days
- Long Polling: 20 seconds
- Dead Letter Queue: Enabled after 3 receives

**Message Format**:
```json
{
  "bucketName": "acme-static-assets",
  "objectKey": "/prod/public/images/logo.png",
  "originPath": "/prod/public",
  "stageId": "prod",
  "eventTime": "2025-12-09T10:30:00.000Z",
  "eventType": "ObjectCreated:Put"
}
```

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

### Benefits

- **Cost Savings**: No constant cron job running
- **Efficient Batching**: Multiple events processed together
- **Reduced API Calls**: Path consolidation across all events in window
- **Scalable**: Handles bursts of S3 events gracefully

## Path Consolidation Algorithm

The path consolidation algorithm reduces the number of invalidation paths by replacing multiple individual paths with directory-level wildcards.

### Consolidation Rules

#### 1. Index and Default File Consolidation

When an event is received for a file matching `*/index.*` or `*/default.*`, the system automatically creates a directory-level invalidation:

```
Input:  /prod/public/docs/index.html
Output: /prod/public/docs/*
```

#### 2. Directory Threshold Consolidation

When more than 3 files in the same directory are modified, consolidate to directory level:

```
Input:  /prod/public/images/logo.png
        /prod/public/images/banner.jpg
        /prod/public/images/icon.svg
        /prod/public/images/background.png
Output: /prod/public/images/*
```

#### 3. Sibling Directory Consolidation

When more than 10 sibling directories would be invalidated, consolidate to parent:

```
Input:  /prod/public/dir1/*
        /prod/public/dir2/*
        /prod/public/dir3/*
        ... (11 directories)
Output: /prod/public/*
```

#### 4. Root Consolidation

When consolidation reaches the origin path root, use `/*`:

```
Input:  Multiple directories at root level
Output: /*
```

#### 5. Request Splitting

If consolidated paths exceed 1000 items (CloudFront limit), split into multiple requests:

```
Input:  1500 paths
Output: Request 1: 1000 paths
        Request 2: 500 paths
```

### Example Consolidation Flow

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

## Required Tags

### S3 Bucket Tags

For an S3 bucket to trigger invalidations, it MUST have the following tag:

```
Key: AllowInvalidationEvents
Value: true
```

**How to Add**:
```bash
aws s3api put-bucket-tagging \
  --bucket your-bucket-name \
  --tagging 'TagSet=[{Key=AllowInvalidationEvents,Value=true}]'
```

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
```bash
aws cloudfront tag-resource \
  --resource arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE \
  --tags 'Items=[{Key=AllowInvalidationEvents,Value=true},{Key=atlantis:ApplicationDeploymentId,Value=acme-static-assets-prod}]'
```

### Tag Validation Flow

1. **Bucket Validation**: Processor checks S3 bucket tags before processing events
2. **Distribution Discovery**: Processor finds distributions matching bucket origin
3. **Distribution Validation**: Processor checks distribution tags before submitting invalidation
4. **Skip on Failure**: If tags are missing or incorrect, processing is skipped and logged

## Deployment

### Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed
- Python 3.9 or later
- Access to Atlantis Platform deployment pipeline

### Deployment Steps

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd application-infrastructure
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Build the Application**:
   ```bash
   sam build
   ```

4. **Deploy to TEST Environment**:
   ```bash
   sam deploy \
     --stack-name atlantis-cloudfront-invalidation-test \
     --parameter-overrides \
       DeployEnvironment=TEST \
       Prefix=atlantis \
       ProjectId=cloudfront-invalidation \
       StageId=test
   ```

5. **Deploy to PROD Environment**:
   ```bash
   sam deploy \
     --stack-name atlantis-cloudfront-invalidation-prod \
     --parameter-overrides \
       DeployEnvironment=PROD \
       Prefix=atlantis \
       ProjectId=cloudfront-invalidation \
       StageId=prod \
       AlarmNotificationEmail=ops@example.com \
       FunctionGradualDeploymentType=Linear10PercentEvery1Minute
   ```

### Configure S3 Bucket Notifications

After deployment, configure your S3 buckets to send events to the Ingestor Lambda:

```bash
# Get the Ingestor Lambda ARN from CloudFormation outputs
INGESTOR_ARN=$(aws cloudformation describe-stacks \
  --stack-name atlantis-cloudfront-invalidation-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`IngestorLambdaArn`].OutputValue' \
  --output text)

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

### Environment Variables

#### Ingestor Lambda
- `QUEUE_URL`: SQS queue URL for event messages
- `TRACKING_TABLE`: DynamoDB table name for window tracking
- `PROCESSOR_FUNCTION_ARN`: ARN of Processor Lambda
- `AGGREGATION_WINDOW_SECONDS`: Window duration (default: 300)
- `LOG_LEVEL`: INFO (PROD) or DEBUG (TEST/DEV)

#### Processor Lambda
- `QUEUE_URL`: SQS queue URL for event messages
- `TRACKING_TABLE`: DynamoDB table name for window tracking
- `MAX_BATCH_SIZE`: SQS batch size (default: 10)
- `MAX_PATHS_PER_INVALIDATION`: CloudFront limit (1000)
- `LOG_LEVEL`: INFO (PROD) or DEBUG (TEST/DEV)

### CloudFormation Parameters

- `DeployEnvironment`: PROD, TEST, or DEV
- `Prefix`: Resource naming prefix (e.g., "atlantis")
- `ProjectId`: Project identifier
- `StageId`: Stage identifier (prod, test, dev)
- `AlarmNotificationEmail`: Email for CloudWatch Alarms (PROD only)
- `FunctionGradualDeploymentType`: Deployment strategy (PROD only)
- `LogRetentionInDaysForPROD`: Log retention for PROD (default: 90)
- `LogRetentionInDaysForDEVTEST`: Log retention for TEST/DEV (default: 7)

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

**Solution**: Adjust consolidation thresholds or reduce S3 event frequency

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
pytest src/tests/unit/ -v
```

### Property-Based Tests

Run property-based tests using Hypothesis:

```bash
pytest src/tests/property/ -v
```

### Integration Tests

Run integration tests against real AWS services:

```bash
# Set AWS credentials for TEST environment
export AWS_PROFILE=test

# Run integration tests
pytest src/tests/integration/ -v
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

**Estimated Monthly Costs** (for moderate usage):
- Lambda Invocations: $5-10
- SQS Messages: $1-2
- DynamoDB: $1-2 (on-demand)
- CloudWatch Logs: $2-5
- CloudFront Invalidations: $0.005 per path (first 1000 free)
- EventBridge Scheduler: $0.01 per invocation

**Total**: ~$10-20/month (excluding CloudFront invalidation costs)

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

- [AWS Serverless Application Model (SAM)](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)
- [CloudFront Invalidation API](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Invalidation.html)
- [EventBridge Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html)
- [Atlantis Platform Documentation](https://github.com/63klabs/serverless-deploy-pipeline-atlantis)

## Support

For issues, questions, or contributions:
- Review CloudWatch Logs for error details
- Check DLQ for failed messages
- Review X-Ray traces for performance issues
- Contact platform team for assistance

## License

This project is part of the Atlantis Platform and follows the platform's licensing terms.
