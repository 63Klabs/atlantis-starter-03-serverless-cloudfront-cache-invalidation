# Requirements Document

## Introduction

This specification defines an event-driven, decoupled, multi-bucket CloudFront invalidation service for the Atlantis Platform. The system listens to S3 object-change events from buckets fronted by CloudFront via Object Access Control (OAC), aggregates paths across events, consolidates invalidation requests according to defined rules, and submits CloudFront invalidations on an on-demand schedule (approximately every 5 minutes) without running a constant cron job. The system must support multiple S3 buckets and CloudFront distributions while maintaining tag-based security isolation and following Atlantis Platform naming conventions.

## Glossary

- **Invalidation Service**: The complete serverless application stack that processes S3 events and creates CloudFront invalidations
- **Ingestor Lambda**: A lightweight Lambda function that receives S3 events, filters them, and queues valid events for processing
- **Processor Lambda**: A Lambda function that processes queued events, aggregates paths, validates permissions via tags, and submits invalidation requests to CloudFront
- **Aggregation Window**: A time period (approximately 5 minutes) during which S3 events are collected before processing
- **Origin Path**: The path prefix in S3 structured as `/<StageId>/public` that corresponds to a CloudFront origin
- **StageId**: A deployment instance identifier (test, beta, stage, prod) used in resource naming and path structures
- **Consolidation Algorithm**: Logic that reduces the number of invalidation paths by replacing multiple individual paths with directory-level wildcards
- **Event Queue**: An SQS Standard queue that stores S3 event data for batch processing
- **Dead Letter Queue**: An SQS queue that captures failed messages from the Event Queue for retry or investigation
- **Scheduler**: A mechanism (EventBridge Scheduler or DynamoDB-based tracking) that triggers the Processor Lambda after the aggregation window
- **AllowInvalidationEvents Tag**: A resource tag that must be set to "true" on both S3 buckets and CloudFront distributions to enable invalidation processing
- **Atlantis Platform**: The 63Klabs serverless deployment framework that enforces naming conventions, tagging, and IAM policies

## Requirements

### Requirement 1

**User Story:** As a platform engineer, I want the Invalidation Service to receive S3 object-change events from multiple buckets, so that any bucket can trigger cache invalidations without tight coupling.

#### Acceptance Criteria

1. WHEN an S3 bucket sends a PUT, POST, COPY, or DELETE event to the Ingestor Lambda THEN the Invalidation Service SHALL extract bucketName, objectKey, eventTime, and eventType from the event
2. WHEN the Ingestor Lambda receives an S3 event THEN the Invalidation Service SHALL parse the objectKey to extract the StageId from the first path segment
3. WHEN the Ingestor Lambda processes an event THEN the Invalidation Service SHALL log the event details in JSON format including bucketName, originPath, stageId, and objectKey
4. WHEN the Ingestor Lambda successfully processes an event THEN the Invalidation Service SHALL return a success response to S3

### Requirement 2

**User Story:** As a platform engineer, I want the Ingestor Lambda to filter events based on production environments and public paths, so that only relevant events are queued for processing.

#### Acceptance Criteria

1. WHEN the Ingestor Lambda receives an event with a StageId starting with 'p', 's', or 'b' THEN the Invalidation Service SHALL proceed with processing
2. WHEN the Ingestor Lambda receives an event with a StageId not starting with 'p', 's', or 'b' THEN the Invalidation Service SHALL ignore the event and log the reason
3. WHEN the Ingestor Lambda receives an event with an objectKey matching the pattern `/<StageId>/public/*` THEN the Invalidation Service SHALL proceed with processing
4. WHEN the Ingestor Lambda receives an event with an objectKey not matching `/<StageId>/public/*` THEN the Invalidation Service SHALL ignore the event and log the reason

### Requirement 3

**User Story:** As a platform engineer, I want filtered S3 events to be queued in SQS, so that events can be aggregated and processed in batches.

#### Acceptance Criteria

1. WHEN the Ingestor Lambda validates an S3 event THEN the Invalidation Service SHALL send a message to the Event Queue containing bucketName, objectKey, originPath, stageId, and eventTime
2. WHEN the Ingestor Lambda fails to send a message to the Event Queue after retries THEN the Invalidation Service SHALL log the failure and raise an exception
3. WHEN a message fails processing in the Event Queue THEN the Invalidation Service SHALL move the message to the Dead Letter Queue after the maximum receive count is exceeded
4. WHEN the Event Queue receives messages THEN the Invalidation Service SHALL store them for batch retrieval by the Processor Lambda

### Requirement 4

**User Story:** As a platform engineer, I want the first event in an aggregation window to trigger a one-time scheduled invocation, so that invalidations are processed efficiently without a constant cron job.

#### Acceptance Criteria

1. WHEN the Ingestor Lambda processes the first event within an aggregation window THEN the Invalidation Service SHALL create a one-time schedule to invoke the Processor Lambda after 5 minutes
2. WHEN the Ingestor Lambda processes subsequent events within an active aggregation window THEN the Invalidation Service SHALL not create additional schedules
3. WHEN the scheduled time arrives THEN the Invalidation Service SHALL invoke the Processor Lambda to process all queued events from all origins
4. WHEN the Processor Lambda completes processing THEN the Invalidation Service SHALL mark the aggregation window as closed

### Requirement 5

**User Story:** As a platform engineer, I want the Processor Lambda to retrieve and batch process messages from the Event Queue, so that multiple events can be handled efficiently.

#### Acceptance Criteria

1. WHEN the Processor Lambda is invoked by the scheduler THEN the Invalidation Service SHALL retrieve messages from the Event Queue in batches
2. WHEN the Processor Lambda retrieves messages THEN the Invalidation Service SHALL group events by bucketName and originPath
3. WHEN the Processor Lambda successfully processes a message THEN the Invalidation Service SHALL delete the message from the Event Queue
4. WHEN the Processor Lambda fails to process a message after retries THEN the Invalidation Service SHALL leave the message on the queue for Dead Letter Queue handling

### Requirement 6

**User Story:** As a platform engineer, I want the Processor Lambda to validate bucket permissions using tags, so that only authorized buckets can trigger invalidations.

#### Acceptance Criteria

1. WHEN the Processor Lambda processes events for a bucket THEN the Invalidation Service SHALL retrieve the bucket tags using GetBucketTagging
2. WHEN a bucket has the AllowInvalidationEvents tag with value "true" THEN the Invalidation Service SHALL proceed with processing events for that bucket
3. WHEN a bucket does not have the AllowInvalidationEvents tag or the value is not "true" THEN the Invalidation Service SHALL skip processing and log the reason
4. WHEN the Processor Lambda fails to retrieve bucket tags THEN the Invalidation Service SHALL log the error and skip processing for that bucket

### Requirement 7

**User Story:** As a platform engineer, I want the Processor Lambda to resolve CloudFront distributions by matching bucket origins and paths, so that invalidations target the correct distributions.

#### Acceptance Criteria

1. WHEN the Processor Lambda processes events for a bucket and originPath THEN the Invalidation Service SHALL search all CloudFront distributions for matching origins
2. WHEN a CloudFront distribution has an origin with domainName matching the bucket (regional or global S3 domain) and originPath matching the event originPath THEN the Invalidation Service SHALL identify that distribution as a target
3. WHEN multiple CloudFront distributions match the bucket and originPath THEN the Invalidation Service SHALL target all matching distributions
4. WHEN no CloudFront distributions match the bucket and originPath THEN the Invalidation Service SHALL log the result and skip invalidation for that bucket

### Requirement 8

**User Story:** As a platform engineer, I want the Processor Lambda to validate CloudFront distribution permissions using tags, so that only authorized distributions receive invalidation requests.

#### Acceptance Criteria

1. WHEN the Processor Lambda identifies a matching CloudFront distribution THEN the Invalidation Service SHALL retrieve the distribution tags
2. WHEN a distribution has the AllowInvalidationEvents tag with value "true" and the atlantis:ApplicationDeploymentId tag matching the pattern `<bucket-atlantis:Application>-<StageId>` THEN the Invalidation Service SHALL proceed with invalidation
3. WHEN a distribution does not have the AllowInvalidationEvents tag set to "true" or the atlantis:ApplicationDeploymentId does not match THEN the Invalidation Service SHALL skip invalidation and log the reason
4. WHEN the Processor Lambda fails to retrieve distribution tags THEN the Invalidation Service SHALL log the error and skip invalidation for that distribution

### Requirement 9

**User Story:** As a platform engineer, I want the Processor Lambda to consolidate invalidation paths using a threshold-based algorithm, so that the number of invalidation requests is minimized.

#### Acceptance Criteria

1. WHEN an event is received for an object matching the pattern `*/index.*` or `*/default.*` THEN the Invalidation Service SHALL automatically create a directory-level invalidation for the parent directory using the pattern `/parent/*`
2. WHEN more than 3 events are received for objects within a single parent directory THEN the Invalidation Service SHALL consolidate those paths into a single directory-level invalidation using the pattern `/parent/*`
3. WHEN more than 10 sibling directories would individually receive directory-level invalidations THEN the Invalidation Service SHALL consolidate to their parent directory
4. WHEN consolidation reaches the root of the originPath THEN the Invalidation Service SHALL use `/*` as the invalidation path
5. WHEN the consolidated paths for a distribution exceed 1000 items THEN the Invalidation Service SHALL split the invalidation into multiple CreateInvalidation requests
6. WHEN a higher-level directory is marked with a wildcard THEN the Invalidation Service SHALL remove all subdirectory paths that are already covered by the parent wildcard

### Requirement 10

**User Story:** As a platform engineer, I want the Processor Lambda to submit CreateInvalidation requests to CloudFront distributions, so that cached content is refreshed.

#### Acceptance Criteria

1. WHEN the Processor Lambda has validated a distribution and consolidated paths THEN the Invalidation Service SHALL submit a CreateInvalidation request with the consolidated paths
2. WHEN a CreateInvalidation request succeeds THEN the Invalidation Service SHALL log the invalidation ID and status in JSON format
3. WHEN a CreateInvalidation request fails THEN the Invalidation Service SHALL retry with exponential backoff
4. WHEN a CreateInvalidation request fails after all retries THEN the Invalidation Service SHALL log the failure in JSON format and continue processing other distributions

### Requirement 11

**User Story:** As a platform engineer, I want all Lambda functions to follow Atlantis Platform naming conventions and tagging requirements, so that resources are properly organized and secured.

#### Acceptance Criteria

1. WHEN Lambda functions are created THEN the Invalidation Service SHALL name them using the pattern `<Prefix>-<ProjectId>-<StageId>-<ResourceName>`
2. WHEN IAM roles are created THEN the Invalidation Service SHALL name them using the pattern `<Prefix>-<ProjectId>-<StageId>-<RoleName>` and apply the configured RolePath
3. WHEN SQS queues are created THEN the Invalidation Service SHALL name them using the pattern `<Prefix>-<ProjectId>-<StageId>-<QueueName>`
4. WHEN resources are created THEN the Invalidation Service SHALL apply the AllowCloudFrontCacheInvalidation tag with value "true" where applicable

### Requirement 12

**User Story:** As a platform engineer, I want Lambda functions to use least-privilege IAM policies scoped to Atlantis naming conventions and tags, so that security is maintained.

#### Acceptance Criteria

1. WHEN the Ingestor Lambda requires SQS permissions THEN the Invalidation Service SHALL grant SendMessage only to the Event Queue ARN
2. WHEN the Processor Lambda requires SQS permissions THEN the Invalidation Service SHALL grant ReceiveMessage, DeleteMessage, and GetQueueAttributes only to the Event Queue ARN
3. WHEN the Processor Lambda requires S3 permissions THEN the Invalidation Service SHALL grant GetBucketTagging only to buckets matching the Prefix naming pattern and having the AllowInvalidationEvents tag
4. WHEN the Processor Lambda requires CloudFront permissions THEN the Invalidation Service SHALL grant ListDistributions and GetDistribution globally, and CreateInvalidation only to distributions with the AllowCloudFrontCacheInvalidation tag

### Requirement 13

**User Story:** As a platform engineer, I want CloudWatch Logs to capture all Lambda execution logs with appropriate retention policies, so that debugging and auditing are supported.

#### Acceptance Criteria

1. WHEN Lambda functions execute in a PROD environment THEN the Invalidation Service SHALL retain CloudWatch Logs for the configured PROD retention period
2. WHEN Lambda functions execute in a TEST or DEV environment THEN the Invalidation Service SHALL retain CloudWatch Logs for the configured TEST/DEV retention period
3. WHEN Lambda functions log messages THEN the Invalidation Service SHALL use JSON format for structured logging
4. WHEN Lambda functions log messages in PROD THEN the Invalidation Service SHALL use INFO level, and in TEST/DEV SHALL use DEBUG level

### Requirement 14

**User Story:** As a platform engineer, I want CloudWatch Alarms to monitor Lambda errors in production, so that failures are detected and reported.

#### Acceptance Criteria

1. WHEN the DeployEnvironment is PROD THEN the Invalidation Service SHALL create CloudWatch Alarms for Lambda function errors
2. WHEN a Lambda function error count exceeds the threshold THEN the Invalidation Service SHALL trigger the alarm and send notifications via SNS
3. WHEN the DeployEnvironment is TEST or DEV THEN the Invalidation Service SHALL not create CloudWatch Alarms to reduce costs
4. WHEN an alarm is triggered THEN the Invalidation Service SHALL send an email notification to the configured AlarmNotificationEmail address
