# Design Document

## Overview

The Multi-Bucket CloudFront Invalidation Service is an event-driven, serverless application that automatically invalidates CloudFront cache entries when objects are updated in S3 buckets. The system is designed to be decoupled from specific buckets and distributions, using tag-based discovery and validation to support multiple applications within the Atlantis Platform framework.

The architecture consists of two primary Lambda functions (Ingestor and Processor), an SQS queue for event aggregation, and a DynamoDB table for tracking aggregation windows. The system processes S3 events, filters them based on environment and path patterns, aggregates them over a 5-minute window, consolidates invalidation paths to minimize API calls, and submits invalidation requests to the appropriate CloudFront distributions.

Key design principles:
- **Decoupled**: Single stack supports any number of S3 buckets and CloudFront distributions
- **Tag-driven**: Uses AWS resource tags for permission validation and resource discovery
- **Efficient**: Aggregates events and consolidates paths to minimize CloudFront API calls
- **Secure**: Implements least-privilege IAM policies with tag-based conditions
- **Cost-effective**: Uses on-demand scheduling instead of constant cron jobs

## Architecture

### High-Level Architecture

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

### Component Interaction Flow

1. **Event Ingestion**: S3 bucket sends object-change event to Ingestor Lambda
2. **Filtering**: Ingestor validates StageId (prod/stage/beta) and path pattern (`/<StageId>/public/*`)
3. **Queuing**: Valid events are sent to SQS Standard queue
4. **Window Tracking**: Ingestor checks DynamoDB for active aggregation window
5. **Scheduling**: If no active window, create EventBridge one-time schedule for +5 minutes
6. **Aggregation**: Events accumulate in SQS queue during 5-minute window
7. **Processing**: Processor Lambda is invoked by EventBridge Scheduler
8. **Batch Retrieval**: Processor reads all messages from SQS in batches
9. **Grouping**: Events are grouped by bucket and originPath
10. **Tag Validation**: Bucket and distribution tags are validated
11. **Path Consolidation**: Paths are consolidated using threshold algorithm
12. **Invalidation**: CreateInvalidation requests are submitted to CloudFront
13. **Cleanup**: Processed messages are deleted from SQS, window is closed in DynamoDB

## Components and Interfaces

### 1. Ingestor Lambda Function

**Purpose**: Receives S3 events, filters them, queues valid events, and manages aggregation window scheduling.

**Handler**: `ingestor.handler(event, context)`

**Input**: S3 Event Notification
```json
{
  "Records": [{
    "eventName": "ObjectCreated:Put",
    "eventTime": "2025-12-09T10:30:00.000Z",
    "s3": {
      "bucket": {"name": "acme-static-assets"},
      "object": {"key": "prod/public/images/logo.png"}
    }
  }]
}
```

**Output**: Success/Failure response to S3

**Key Functions**:
- `filter_event(record)`: Validates StageId and path pattern
- `extract_metadata(record)`: Extracts bucket, key, originPath, stageId
- `send_to_queue(metadata)`: Sends message to SQS
- `check_aggregation_window()`: Queries DynamoDB for active window
- `create_schedule()`: Creates EventBridge one-time schedule

**Environment Variables**:
- `QUEUE_URL`: SQS queue URL
- `TRACKING_TABLE`: DynamoDB table name
- `PROCESSOR_FUNCTION_ARN`: ARN of Processor Lambda
- `AGGREGATION_WINDOW_SECONDS`: Window duration (default: 300)

### 2. Processor Lambda Function

**Purpose**: Processes queued events, validates permissions, consolidates paths, and submits CloudFront invalidations.

**Handler**: `processor.handler(event, context)`

**Input**: EventBridge Scheduler invocation (empty event)

**Output**: Processing summary with success/failure counts

**Key Functions**:
- `receive_messages_batch()`: Retrieves messages from SQS
- `group_by_bucket_and_origin(messages)`: Groups events
- `validate_bucket_tags(bucket_name)`: Checks S3 bucket tags
- `find_distributions(bucket, origin_path)`: Searches CloudFront distributions
- `validate_distribution_tags(distribution_id, bucket_app_tag, stage_id)`: Checks distribution tags
- `consolidate_paths(paths)`: Applies consolidation algorithm
- `submit_invalidation(distribution_id, paths)`: Creates CloudFront invalidation
- `close_aggregation_window()`: Updates DynamoDB tracking table

**Environment Variables**:
- `QUEUE_URL`: SQS queue URL
- `TRACKING_TABLE`: DynamoDB table name
- `MAX_BATCH_SIZE`: SQS batch size (default: 10)
- `MAX_PATHS_PER_INVALIDATION`: CloudFront limit (1000)

### 3. SQS Event Queue

**Type**: Standard Queue (higher throughput, no ordering guarantee)

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

**Configuration**:
- Visibility Timeout: 300 seconds (5 minutes)
- Message Retention: 4 days
- Receive Message Wait Time: 20 seconds (long polling)
- Dead Letter Queue: Enabled after 3 receives

### 4. SQS Dead Letter Queue

**Purpose**: Captures messages that fail processing after maximum retries

**Configuration**:
- Message Retention: 14 days
- Alarm: Trigger when message count > 0

### 5. DynamoDB Tracking Table

**Purpose**: Tracks active aggregation windows to prevent duplicate scheduling

**Table Schema**:
- Partition Key: `windowId` (String) - Fixed value "current"
- Attributes:
  - `scheduleArn` (String) - EventBridge Schedule ARN
  - `windowStartTime` (Number) - Unix timestamp
  - `windowEndTime` (Number) - Unix timestamp
  - `status` (String) - "active" or "closed"
- TTL: `windowEndTime` + 1 hour (automatic cleanup)

**Access Patterns**:
- Check for active window: Query by `windowId` where `status = "active"`
- Create window: PutItem with condition `attribute_not_exists(windowId) OR status = "closed"`
- Close window: UpdateItem set `status = "closed"`

### 6. EventBridge Scheduler

**Purpose**: Creates one-time schedules to invoke Processor Lambda after aggregation window

**Schedule Configuration**:
- Schedule Expression: `at(YYYY-MM-DDTHH:MM:SS)` (one-time)
- Target: Processor Lambda ARN
- Flexible Time Window: None (exact time)
- Retry Policy: 0 retries (Lambda handles retries internally)
- Auto-delete: After completion

**Scheduler Selection Rationale**:

After evaluating both options:

**Option 1: EventBridge Scheduler** (RECOMMENDED)
- ✅ Purpose-built for one-time scheduled invocations
- ✅ Automatically deletes schedule after execution
- ✅ No additional state management required
- ✅ Simple API: CreateSchedule with `at()` expression
- ✅ Native Lambda integration
- ✅ Lower complexity

**Option 2: DynamoDB + Conditional Logic**
- ❌ Requires additional state management logic
- ❌ More complex error handling
- ❌ Need to handle race conditions
- ❌ Manual cleanup of tracking records
- ✅ Slightly lower cost (but negligible at scale)

**Decision**: Use EventBridge Scheduler for simplicity and purpose-fit. The DynamoDB table will only track whether a schedule exists, not implement the scheduling itself.

## Data Models

### S3 Event Message (SQS)

```python
class S3EventMessage:
    bucket_name: str          # S3 bucket name
    object_key: str           # Full S3 object key
    origin_path: str          # Extracted origin path (/<StageId>/public)
    stage_id: str             # Extracted StageId
    event_time: str           # ISO 8601 timestamp
    event_type: str           # S3 event type
```

### Aggregation Window (DynamoDB)

```python
class AggregationWindow:
    window_id: str            # Partition key (fixed: "current")
    schedule_arn: str         # EventBridge Schedule ARN
    window_start_time: int    # Unix timestamp
    window_end_time: int      # Unix timestamp (TTL)
    status: str               # "active" or "closed"
```

### Distribution Match

```python
class DistributionMatch:
    distribution_id: str      # CloudFront distribution ID
    bucket_name: str          # Matched S3 bucket
    origin_path: str          # Matched origin path
    app_deployment_id: str    # Expected tag value
    is_valid: bool            # Tag validation result
```

### Consolidated Paths

```python
class ConsolidatedPaths:
    distribution_id: str      # Target distribution
    paths: List[str]          # Consolidated invalidation paths
    original_count: int       # Original path count
    consolidated_count: int   # After consolidation
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Event Parsing and Extraction Properties

Property 1: S3 event field extraction completeness
*For any* valid S3 event notification, parsing the event should successfully extract bucketName, objectKey, eventTime, and eventType without errors
**Validates: Requirements 1.1**

Property 2: StageId extraction from object key
*For any* object key with at least one path segment, extracting the StageId should return the first non-empty segment after the leading slash
**Validates: Requirements 1.2**

Property 3: Event logging contains required fields
*For any* processed S3 event, the JSON log output should contain the fields bucketName, originPath, stageId, and objectKey
**Validates: Requirements 1.3**

### Event Filtering Properties

Property 4: Production StageId filter acceptance
*For any* StageId starting with 'p', 's', or 'b' (case-insensitive), the filter should accept the event for processing
**Validates: Requirements 2.1**

Property 5: Non-production StageId filter rejection
*For any* StageId not starting with 'p', 's', or 'b', the filter should reject the event and log the rejection reason
**Validates: Requirements 2.2**

Property 6: Public path pattern acceptance
*For any* object key matching the pattern `/<StageId>/public/*`, the path filter should accept the event for processing
**Validates: Requirements 2.3**

Property 7: Non-public path pattern rejection
*For any* object key not matching the pattern `/<StageId>/public/*`, the path filter should reject the event and log the rejection reason
**Validates: Requirements 2.4**

### Message Queuing Properties

Property 8: SQS message format completeness
*For any* validated S3 event, the SQS message should contain all required fields: bucketName, objectKey, originPath, stageId, and eventTime
**Validates: Requirements 3.1**

### Aggregation Window Properties

Property 9: Schedule creation for first event
*For any* event processed when no active aggregation window exists, a new EventBridge schedule should be created with a target time 5 minutes in the future
**Validates: Requirements 4.1**

Property 10: Schedule prevention for subsequent events
*For any* event processed when an active aggregation window exists, no new EventBridge schedule should be created
**Validates: Requirements 4.2**

Property 11: Window closure after processing
*For any* completed Processor Lambda execution, the aggregation window status in DynamoDB should be updated to "closed"
**Validates: Requirements 4.4**

### Message Processing Properties

Property 12: Event grouping by bucket and origin
*For any* set of SQS messages, grouping them by bucketName and originPath should result in groups where all messages in each group share the same bucketName and originPath
**Validates: Requirements 5.2**

Property 13: Message deletion after successful processing
*For any* SQS message that is successfully processed, the message should be deleted from the queue
**Validates: Requirements 5.3**

### Tag Validation Properties

Property 14: Bucket tag validation for allowed buckets
*For any* bucket with the AllowInvalidationEvents tag set to "true", the tag validation should return true and allow processing
**Validates: Requirements 6.2**

Property 15: Bucket tag validation for disallowed buckets
*For any* bucket without the AllowInvalidationEvents tag or with a value other than "true", the tag validation should return false and skip processing
**Validates: Requirements 6.3**

Property 16: Distribution tag validation for allowed distributions
*For any* CloudFront distribution with AllowInvalidationEvents="true" and atlantis:ApplicationDeploymentId matching `<bucket-app-tag>-<StageId>`, the tag validation should return true and allow invalidation
**Validates: Requirements 8.2**

Property 17: Distribution tag validation for disallowed distributions
*For any* CloudFront distribution without AllowInvalidationEvents="true" or with mismatched atlantis:ApplicationDeploymentId, the tag validation should return false and skip invalidation
**Validates: Requirements 8.3**

### Distribution Discovery Properties

Property 18: Distribution matching by origin
*For any* bucket name and origin path, searching CloudFront distributions should return all distributions where an origin's domainName matches the bucket (regional or global S3 domain) and originPath matches the event origin path
**Validates: Requirements 7.2**

Property 19: Multiple distribution targeting
*For any* bucket and origin path that match multiple CloudFront distributions, all matching distributions should be included in the target list
**Validates: Requirements 7.3**

### Path Consolidation Properties

Property 20: Index and default file directory consolidation
*For any* object path ending with `/index.*` or `/default.*`, the consolidation algorithm should replace the file path with the parent directory path followed by `/*`
**Validates: Requirements 9.1**

Property 21: Directory consolidation threshold
*For any* set of object paths where more than 3 paths share the same parent directory, the consolidation algorithm should replace those paths with a single directory-level path `<parent>/*`
**Validates: Requirements 9.2**

Property 22: Sibling directory consolidation
*For any* set of directory-level paths where more than 3 sibling directories would be invalidated, the consolidation algorithm should replace them with their parent directory path followed by `/*`
**Validates: Requirements 9.3**

Property 23: Root consolidation terminal case
*For any* consolidation that reaches the origin path root, the final consolidated path should be `/*`
**Validates: Requirements 9.4**

Property 24: Invalidation request splitting
*For any* consolidated path list exceeding 1000 items, the paths should be split into multiple lists where each list contains at most 1000 items
**Validates: Requirements 9.5**

### Invalidation Submission Properties

Property 25: CreateInvalidation API call correctness
*For any* validated distribution and consolidated path list, the CreateInvalidation request should include the distribution ID and the exact consolidated paths
**Validates: Requirements 10.1**

Property 26: Successful invalidation logging
*For any* successful CreateInvalidation response, the log output should be valid JSON containing the invalidation ID and status
**Validates: Requirements 10.2**

### Logging Properties

Property 27: JSON log format validity
*For any* log message produced by the Lambda functions, the message should be valid JSON that can be parsed without errors
**Validates: Requirements 13.3**

## Error Handling

### Ingestor Lambda Error Handling

1. **S3 Event Parsing Errors**
   - Catch: Malformed S3 event structure
   - Action: Log error with event details, return failure to S3
   - Retry: S3 will retry based on bucket notification configuration

2. **SQS Send Failures**
   - Catch: SQS service unavailable, throttling, or network errors
   - Action: Retry with exponential backoff (3 attempts)
   - Fallback: Log error and raise exception to trigger S3 retry

3. **DynamoDB Access Errors**
   - Catch: DynamoDB service unavailable, throttling, or permission errors
   - Action: Retry with exponential backoff (3 attempts)
   - Fallback: Log error but continue processing (schedule creation is best-effort)

4. **EventBridge Scheduler Errors**
   - Catch: Scheduler service unavailable or permission errors
   - Action: Retry with exponential backoff (3 attempts)
   - Fallback: Log error but continue processing (events will still be queued)

### Processor Lambda Error Handling

1. **SQS Receive Errors**
   - Catch: SQS service unavailable or network errors
   - Action: Retry with exponential backoff (3 attempts)
   - Fallback: Log error and exit (EventBridge will not retry, next window will process)

2. **S3 GetBucketTagging Errors**
   - Catch: Bucket not found, permission denied, or service errors
   - Action: Log error and skip bucket
   - Continue: Process other buckets in batch

3. **CloudFront ListDistributions Errors**
   - Catch: Service unavailable or permission errors
   - Action: Retry with exponential backoff (3 attempts)
   - Fallback: Log error and skip bucket

4. **CloudFront GetDistribution Errors**
   - Catch: Distribution not found or service errors
   - Action: Log error and skip distribution
   - Continue: Process other distributions

5. **CloudFront CreateInvalidation Errors**
   - Catch: Service unavailable, throttling, or invalid request
   - Action: Retry with exponential backoff (5 attempts with jitter)
   - Fallback: Log error and continue with other distributions

6. **DynamoDB Update Errors**
   - Catch: Service unavailable or permission errors
   - Action: Retry with exponential backoff (3 attempts)
   - Fallback: Log error but consider processing successful (cleanup is best-effort)

### Dead Letter Queue Handling

- Messages that fail processing after 3 receives are moved to DLQ
- CloudWatch Alarm triggers when DLQ message count > 0
- Manual investigation required for DLQ messages
- Common causes: Malformed messages, permission issues, or persistent service outages

### Retry Strategy

**Exponential Backoff Configuration**:
- Initial delay: 100ms
- Maximum delay: 5 seconds
- Backoff multiplier: 2
- Jitter: ±25% random variation

**Retry Limits**:
- SQS operations: 3 retries
- DynamoDB operations: 3 retries
- S3 GetBucketTagging: No retries (skip bucket on failure)
- CloudFront ListDistributions: 3 retries
- CloudFront CreateInvalidation: 5 retries with jitter

## Testing Strategy

### Unit Testing

Unit tests will verify individual functions and components in isolation using mocked AWS services. Focus areas:

1. **Event Parsing and Filtering**
   - Test S3 event structure parsing
   - Test StageId extraction from various path formats
   - Test production environment filtering (p*, s*, b*)
   - Test public path pattern matching
   - Test edge cases: empty paths, malformed keys, missing fields

2. **Path Consolidation Algorithm**
   - Test index.* and default.* file detection
   - Test directory consolidation with various thresholds
   - Test sibling directory consolidation
   - Test recursive consolidation to root
   - Test path splitting at 1000-item limit
   - Test edge cases: empty path lists, single paths, deeply nested structures

3. **Tag Validation Logic**
   - Test bucket tag validation with various tag combinations
   - Test distribution tag validation with pattern matching
   - Test ApplicationDeploymentId format validation
   - Test edge cases: missing tags, null values, incorrect types

4. **Distribution Matching**
   - Test bucket domain matching (regional vs global)
   - Test origin path matching
   - Test multiple distribution handling
   - Test edge cases: no matches, partial matches

5. **Message Grouping**
   - Test grouping by bucket and origin path
   - Test handling of mixed message types
   - Test edge cases: empty message lists, single messages

6. **Window Tracking**
   - Test active window detection
   - Test schedule creation logic
   - Test window closure logic
   - Test edge cases: concurrent access, expired windows

**Unit Test Framework**: pytest (Python)
**Mocking Library**: boto3 mocking with moto or unittest.mock

### Property-Based Testing

Property-based tests will verify universal properties across randomly generated inputs using Hypothesis (Python). Each property test will run a minimum of 100 iterations.

**Property Test Framework**: Hypothesis for Python

**Test Configuration**:
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@settings(max_examples=100)
@given(...)
def test_property_name(...):
    # Property test implementation
```

**Property Test Coverage**:
- Properties 1-27 as defined in the Correctness Properties section
- Each property will be implemented as a separate test function
- Tests will use Hypothesis strategies to generate random but valid inputs
- Tests will include edge case generation (empty strings, boundary values, etc.)

**Generator Strategies**:
- S3 event structures with valid and invalid fields
- Object keys with various path patterns
- StageId values (valid and invalid)
- Tag dictionaries with various combinations
- Path lists of varying sizes and structures
- Distribution configurations with different origins

### Integration Testing

Integration tests will verify component interactions with real AWS services in a test environment:

1. **End-to-End Event Flow**
   - Send test S3 event to Ingestor Lambda
   - Verify message appears in SQS queue
   - Verify schedule is created in EventBridge
   - Trigger Processor Lambda manually
   - Verify invalidation is submitted to test CloudFront distribution

2. **IAM Permission Validation**
   - Verify Ingestor can write to SQS
   - Verify Processor can read from SQS
   - Verify Processor can read S3 bucket tags
   - Verify Processor can list CloudFront distributions
   - Verify Processor can create invalidations on tagged distributions
   - Verify tag-based conditions work correctly

3. **DynamoDB Window Tracking**
   - Verify window creation on first event
   - Verify window prevents duplicate schedules
   - Verify window closure after processing
   - Verify TTL cleanup

4. **Dead Letter Queue**
   - Trigger message processing failures
   - Verify messages move to DLQ after max receives
   - Verify DLQ alarm triggers

**Integration Test Environment**:
- Dedicated TEST AWS account or isolated resources
- Test S3 bucket with AllowInvalidationEvents tag
- Test CloudFront distribution with appropriate tags
- Test SQS queues and DLQ
- Test DynamoDB table
- Test EventBridge Scheduler permissions

**Integration Test Framework**: pytest with boto3 (real AWS SDK calls)

### Test Data Management

**Mock Data**:
- Sample S3 events for various object types
- Sample bucket and distribution tag configurations
- Sample path structures for consolidation testing

**Test Fixtures**:
- Reusable S3 event templates
- Reusable tag validation scenarios
- Reusable path consolidation test cases

### Testing Best Practices

1. **Separation of Concerns**: Business logic separated from AWS SDK calls for easier mocking
2. **Deterministic Tests**: Use fixed seeds for random generation in property tests
3. **Fast Unit Tests**: Mock all AWS services, no network calls
4. **Isolated Integration Tests**: Use dedicated test resources, clean up after tests
5. **Comprehensive Edge Cases**: Test boundary conditions, empty inputs, malformed data
6. **Clear Test Names**: Use descriptive names that explain what is being tested
7. **Minimal Mocking**: Only mock external dependencies, test real business logic

## Implementation Notes

### Python Code Structure

```
application-infrastructure/
├── src/
│   ├── ingestor/
│   │   ├── __init__.py
│   │   ├── handler.py           # Lambda handler
│   │   ├── event_parser.py      # S3 event parsing
│   │   ├── event_filter.py      # Filtering logic
│   │   ├── queue_client.py      # SQS operations
│   │   ├── window_tracker.py    # DynamoDB window tracking
│   │   └── scheduler_client.py  # EventBridge Scheduler
│   ├── processor/
│   │   ├── __init__.py
│   │   ├── handler.py           # Lambda handler
│   │   ├── queue_client.py      # SQS operations
│   │   ├── tag_validator.py     # Tag validation logic
│   │   ├── distribution_finder.py # CloudFront discovery
│   │   ├── path_consolidator.py # Consolidation algorithm
│   │   └── invalidation_client.py # CloudFront invalidation
│   ├── common/
│   │   ├── __init__.py
│   │   ├── logger.py            # JSON logging utility
│   │   ├── retry.py             # Retry decorator
│   │   └── constants.py         # Shared constants
│   └── tests/
│       ├── unit/
│       │   ├── test_event_parser.py
│       │   ├── test_event_filter.py
│       │   ├── test_path_consolidator.py
│       │   ├── test_tag_validator.py
│       │   └── ...
│       ├── property/
│       │   ├── test_properties_parsing.py
│       │   ├── test_properties_filtering.py
│       │   ├── test_properties_consolidation.py
│       │   └── ...
│       └── integration/
│           ├── test_end_to_end.py
│           ├── test_permissions.py
│           └── ...
├── template.yml                 # CloudFormation/SAM template
└── requirements.txt             # Python dependencies
```

### CloudFormation Template Structure

The template will include:
- Two Lambda functions (Ingestor, Processor)
- Two IAM roles with least-privilege policies
- SQS queue and DLQ
- DynamoDB table for window tracking
- EventBridge Scheduler IAM role
- CloudWatch Log Groups with retention
- CloudWatch Alarms (conditional on PROD)
- SNS Topic for alarms (conditional on PROD)
- Lambda permissions for S3 invocation
- All resources following Atlantis naming conventions

### Environment-Specific Configuration

**PROD Environment**:
- Gradual Lambda deployment enabled
- CloudWatch Alarms enabled
- Log retention: 90 days (configurable)
- Log level: INFO
- X-Ray tracing enabled

**TEST/DEV Environment**:
- All-at-once Lambda deployment
- No CloudWatch Alarms
- Log retention: 7 days (configurable)
- Log level: DEBUG
- X-Ray tracing disabled (DEV only)

### Performance Considerations

1. **SQS Batch Size**: Use maximum batch size (10) for efficient processing
2. **CloudFront API Limits**: Respect 1000 paths per invalidation, 3000 invalidations per distribution per hour
3. **Lambda Timeout**: Ingestor: 10 seconds, Processor: 300 seconds (5 minutes)
4. **Lambda Memory**: Ingestor: 256 MB, Processor: 512 MB
5. **Concurrent Executions**: Ingestor: Unlimited, Processor: 1 (prevent duplicate processing)
6. **DynamoDB Capacity**: On-demand pricing for unpredictable traffic

### Security Considerations

1. **IAM Policies**: All policies use least-privilege with resource-level permissions
2. **Tag-Based Conditions**: IAM policies enforce tag-based access control
3. **Encryption**: SQS queue encrypted at rest, CloudWatch Logs encrypted
4. **No Secrets**: No hardcoded credentials or sensitive data in code
5. **VPC**: Lambda functions do not require VPC access (public AWS services only)
6. **Resource Policies**: S3 buckets grant Lambda invocation permission explicitly

### Cost Optimization

1. **No Constant Cron**: EventBridge Scheduler only runs when needed
2. **Batch Processing**: Aggregate events to minimize Lambda invocations
3. **Path Consolidation**: Reduce CloudFront invalidation costs
4. **DynamoDB TTL**: Automatic cleanup of old window records
5. **Conditional Resources**: Alarms and dashboards only in PROD
6. **Short Log Retention**: 7 days in TEST/DEV to reduce storage costs

### Monitoring and Observability

**CloudWatch Metrics**:
- Lambda invocation count, duration, errors
- SQS message count, age, DLQ count
- DynamoDB read/write capacity
- CloudFront invalidation count

**CloudWatch Logs**:
- Structured JSON logging for easy parsing
- Log groups with appropriate retention
- Log insights queries for debugging

**CloudWatch Alarms** (PROD only):
- Lambda error rate > 1 in 15 minutes
- DLQ message count > 0
- Processor Lambda duration > 4 minutes

**X-Ray Tracing** (PROD/TEST):
- End-to-end request tracing
- Service map visualization
- Performance bottleneck identification

### Deployment Considerations

1. **Gradual Deployment**: PROD uses gradual deployment with automatic rollback on errors
2. **Alias Management**: Lambda aliases (live) for stable invocation
3. **Version Control**: Lambda versions published automatically
4. **Stack Updates**: CloudFormation handles updates with minimal downtime
5. **Rollback**: Automatic rollback on CloudWatch Alarm triggers during deployment
6. **Testing**: Deploy to TEST environment first, validate, then promote to PROD
