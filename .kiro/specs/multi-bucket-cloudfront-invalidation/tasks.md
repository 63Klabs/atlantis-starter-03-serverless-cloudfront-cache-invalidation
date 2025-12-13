# Implementation Plan

- [x] 1. Set up project structure and shared utilities
  - Create directory structure for ingestor, processor, common, and tests modules
  - Implement JSON logger utility with environment-based log levels
  - Implement retry decorator with exponential backoff and jitter
  - Create constants module for shared values (aggregation window, retry limits, etc.)
  - _Requirements: 1.3, 13.3, 13.4_

- [x] 1.1 Write unit tests for shared utilities
  - Test JSON logger output format
  - Test retry decorator with various failure scenarios
  - _Requirements: 13.3_

- [x] 2. Implement S3 event parsing and filtering (Ingestor)
  - Create event_parser module to extract bucketName, objectKey, eventTime, eventType from S3 events
  - Create event_filter module to validate StageId (p*, s*, b*) and path pattern (/<StageId>/public/*)
  - Implement StageId extraction from object key path
  - Implement origin path extraction (/<StageId>/public)
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4_

- [x] 2.1 Write property test for S3 event field extraction
  - **Property 1: S3 event field extraction completeness**
  - **Validates: Requirements 1.1**

- [x] 2.2 Write property test for StageId extraction
  - **Property 2: StageId extraction from object key**
  - **Validates: Requirements 1.2**

- [x] 2.3 Write property test for production StageId filter
  - **Property 4: Production StageId filter acceptance**
  - **Validates: Requirements 2.1**

- [x] 2.4 Write property test for non-production StageId filter
  - **Property 5: Non-production StageId filter rejection**
  - **Validates: Requirements 2.2**

- [x] 2.5 Write property test for public path pattern acceptance
  - **Property 6: Public path pattern acceptance**
  - **Validates: Requirements 2.3**

- [x] 2.6 Write property test for non-public path pattern rejection
  - **Property 7: Non-public path pattern rejection**
  - **Validates: Requirements 2.4**

- [x] 3. Implement SQS queue client (Ingestor)
  - Create queue_client module for SQS operations
  - Implement send_message function with retry logic
  - Format SQS message with bucketName, objectKey, originPath, stageId, eventTime
  - Implement error handling for SQS failures
  - _Requirements: 3.1, 3.2_

- [x] 3.1 Write property test for SQS message format
  - **Property 8: SQS message format completeness**
  - **Validates: Requirements 3.1**

- [x] 4. Implement DynamoDB window tracking (Ingestor)
  - Create window_tracker module for DynamoDB operations
  - Implement check_active_window function to query for active windows
  - Implement create_window function with conditional write (prevent duplicates)
  - Implement close_window function to update status
  - Use TTL for automatic cleanup of old records
  - _Requirements: 4.1, 4.2, 4.4_

- [x] 4.1 Write property test for schedule creation on first event
  - **Property 9: Schedule creation for first event**
  - **Validates: Requirements 4.1**

- [x] 4.2 Write property test for schedule prevention
  - **Property 10: Schedule prevention for subsequent events**
  - **Validates: Requirements 4.2**

- [x] 4.3 Write property test for window closure
  - **Property 11: Window closure after processing**
  - **Validates: Requirements 4.4**

- [x] 5. Implement EventBridge Scheduler client (Ingestor)
  - Create scheduler_client module for EventBridge Scheduler operations
  - Implement create_one_time_schedule function with at() expression
  - Calculate target time as current time + 5 minutes
  - Set target to Processor Lambda ARN
  - Implement error handling for scheduler failures
  - _Requirements: 4.1_

- [x] 6. Implement Ingestor Lambda handler
  - Create handler.py that orchestrates event processing
  - Parse S3 event using event_parser
  - Filter event using event_filter
  - Send valid events to SQS using queue_client
  - Check and create aggregation window using window_tracker and scheduler_client
  - Log all operations in JSON format
  - Return success/failure response to S3
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 4.1, 4.2_

- [x] 6.1 Write property test for event logging format
  - **Property 3: Event logging contains required fields**
  - **Validates: Requirements 1.3**

- [x] 6.2 Write unit tests for Ingestor handler
  - Test successful event processing flow
  - Test event filtering and rejection
  - Test SQS send failures
  - Test window tracking edge cases
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 4.1, 4.2_

- [x] 7. Implement SQS queue client for Processor
  - Create queue_client module in processor package
  - Implement receive_messages_batch function with long polling
  - Implement delete_message function
  - Implement batch delete for efficiency
  - Handle empty queue gracefully
  - _Requirements: 5.1, 5.3_

- [x] 7.1 Write property test for message deletion
  - **Property 13: Message deletion after successful processing**
  - **Validates: Requirements 5.3**

- [x] 8. Implement message grouping logic (Processor)
  - Create message grouping function in handler
  - Group messages by bucketName and originPath
  - Return dictionary with (bucket, origin) as keys and message lists as values
  - _Requirements: 5.2_

- [x] 8.1 Write property test for event grouping
  - **Property 12: Event grouping by bucket and origin**
  - **Validates: Requirements 5.2**

- [x] 9. Implement S3 bucket tag validation (Processor)
  - Create tag_validator module
  - Implement get_bucket_tags function using GetBucketTagging
  - Implement validate_bucket_tags function to check AllowInvalidationEvents=true
  - Handle missing tags and API errors gracefully
  - Log validation results
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 9.1 Write property test for bucket tag validation (allowed)
  - **Property 14: Bucket tag validation for allowed buckets**
  - **Validates: Requirements 6.2**

- [x] 9.2 Write property test for bucket tag validation (disallowed)
  - **Property 15: Bucket tag validation for disallowed buckets**
  - **Validates: Requirements 6.3**

- [x] 10. Implement CloudFront distribution discovery (Processor)
  - Create distribution_finder module
  - Implement list_distributions function using CloudFront API with pagination
  - Implement find_matching_distributions function to match bucket and origin path
  - Handle both regional and global S3 domain formats
  - Return list of matching distribution IDs
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 10.1 Write property test for distribution matching
  - **Property 18: Distribution matching by origin**
  - **Validates: Requirements 7.2**

- [x] 10.2 Write property test for multiple distribution targeting
  - **Property 19: Multiple distribution targeting**
  - **Validates: Requirements 7.3**

- [x] 11. Implement CloudFront distribution tag validation (Processor)
  - Add get_distribution_tags function to tag_validator module
  - Implement validate_distribution_tags function
  - Check AllowInvalidationEvents=true
  - Check atlantis:ApplicationDeploymentId matches pattern <bucket-app>-<StageId>
  - Handle missing tags and API errors gracefully
  - Log validation results
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 11.1 Write property test for distribution tag validation (allowed)
  - **Property 16: Distribution tag validation for allowed distributions**
  - **Validates: Requirements 8.2**

- [x] 11.2 Write property test for distribution tag validation (disallowed)
  - **Property 17: Distribution tag validation for disallowed distributions**
  - **Validates: Requirements 8.3**

- [x] 12. Implement path consolidation algorithm (Processor)
  - Create path_consolidator module with consolidate_paths function
  - Implement index.* and default.* file detection and parent directory consolidation
  - Implement directory threshold consolidation (>3 files in same directory)
  - Implement sibling directory consolidation (>3 sibling directories)
  - Implement recursive consolidation up to root (/*) 
  - Implement path splitting for lists exceeding 1000 items
  - Separate function for testability
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 12.1 Write property test for index/default file consolidation
  - **Property 20: Index and default file directory consolidation**
  - **Validates: Requirements 9.1**

- [x] 12.2 Write property test for directory consolidation threshold
  - **Property 21: Directory consolidation threshold**
  - **Validates: Requirements 9.2**

- [x] 12.3 Write property test for sibling directory consolidation
  - **Property 22: Sibling directory consolidation**
  - **Validates: Requirements 9.3**

- [x] 12.4 Write property test for root consolidation
  - **Property 23: Root consolidation terminal case**
  - **Validates: Requirements 9.4**

- [x] 12.5 Write property test for invalidation request splitting
  - **Property 24: Invalidation request splitting**
  - **Validates: Requirements 9.5**

- [x] 12.6 Write unit tests for path consolidation edge cases
  - Test empty path lists
  - Test single path
  - Test deeply nested structures
  - Test mixed file and directory paths
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 13. Implement CloudFront invalidation client (Processor)
  - Create invalidation_client module
  - Implement create_invalidation function using CreateInvalidation API
  - Generate unique CallerReference using timestamp and UUID
  - Implement retry logic with exponential backoff (5 retries with jitter)
  - Handle API errors and throttling
  - Log invalidation ID and status on success
  - Log errors on failure
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 13.1 Write property test for CreateInvalidation API call
  - **Property 25: CreateInvalidation API call correctness**
  - **Validates: Requirements 10.1**

- [x] 13.2 Write property test for successful invalidation logging
  - **Property 26: Successful invalidation logging**
  - **Validates: Requirements 10.2**

- [x] 14. Implement Processor Lambda handler
  - Create handler.py that orchestrates processing
  - Receive messages from SQS in batches
  - Group messages by bucket and origin path
  - For each group: validate bucket tags, find distributions, validate distribution tags
  - Consolidate paths using path_consolidator
  - Submit invalidations using invalidation_client
  - Delete processed messages from SQS
  - Close aggregation window in DynamoDB
  - Log all operations in JSON format
  - Return processing summary
  - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 4.4_

- [x] 14.1 Write property test for JSON log format validity
  - **Property 27: JSON log format validity**
  - **Validates: Requirements 13.3**

- [x] 14.2 Write unit tests for Processor handler
  - Test successful processing flow
  - Test bucket tag validation failures
  - Test distribution discovery with no matches
  - Test distribution tag validation failures
  - Test path consolidation integration
  - Test invalidation submission
  - _Requirements: 5.1, 5.2, 5.3, 6.2, 6.3, 7.2, 7.3, 8.2, 8.3, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2_

- [x] 15. Create CloudFormation template resources
  - Define Ingestor Lambda function with appropriate timeout (10s) and memory (256MB)
  - Define Processor Lambda function with appropriate timeout (300s) and memory (512MB)
  - Define SQS Standard queue with visibility timeout (300s) and DLQ configuration
  - Define SQS Dead Letter Queue with 14-day retention
  - Define DynamoDB table with windowId partition key and TTL on windowEndTime
  - Define IAM role for Ingestor with SQS SendMessage, DynamoDB PutItem/Query, EventBridge Scheduler CreateSchedule
  - Define IAM role for Processor with SQS ReceiveMessage/DeleteMessage, S3 GetBucketTagging, CloudFront List/Get/CreateInvalidation, DynamoDB UpdateItem
  - Define IAM role for EventBridge Scheduler to invoke Processor Lambda
  - Apply Atlantis naming conventions to all resources
  - Apply AllowCloudFrontCacheInvalidation tag where applicable
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 12.1, 12.2, 12.3, 12.4_

- [x] 16. Implement IAM policies with least privilege
  - Ingestor: SQS SendMessage scoped to Event Queue ARN
  - Ingestor: DynamoDB PutItem/Query/UpdateItem scoped to Tracking Table ARN
  - Ingestor: EventBridge Scheduler CreateSchedule/DeleteSchedule scoped to schedule name pattern
  - Processor: SQS ReceiveMessage/DeleteMessage/GetQueueAttributes scoped to Event Queue ARN
  - Processor: S3 GetBucketTagging scoped to Prefix pattern with tag condition AllowInvalidationEvents=true
  - Processor: CloudFront ListDistributions/GetDistribution globally (no resource-level permissions available)
  - Processor: CloudFront CreateInvalidation scoped to distributions with tag AllowCloudFrontCacheInvalidation=true
  - Processor: DynamoDB UpdateItem scoped to Tracking Table ARN
  - Apply RolePath and PermissionsBoundary parameters
  - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 17. Create CloudWatch Log Groups with retention policies
  - Define Log Group for Ingestor Lambda with environment-based retention
  - Define Log Group for Processor Lambda with environment-based retention
  - PROD: Use LogRetentionInDaysForPROD parameter (default 90 days)
  - TEST/DEV: Use LogRetentionInDaysForDEVTEST parameter (default 7 days)
  - Grant Lambda execution roles permission to write logs
  - _Requirements: 13.1, 13.2_

- [x] 18. Create CloudWatch Alarms and SNS notifications (conditional on PROD)
  - Define CloudWatch Alarm for Ingestor Lambda errors (threshold > 1 in 15 minutes)
  - Define CloudWatch Alarm for Processor Lambda errors (threshold > 1 in 15 minutes)
  - Define CloudWatch Alarm for DLQ message count (threshold > 0)
  - Define CloudWatch Alarm for Processor Lambda duration (threshold > 240 seconds)
  - Define SNS Topic for alarm notifications
  - Add email subscription using AlarmNotificationEmail parameter
  - Use Condition: CreateAlarms (IsProduction)
  - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [x] 19. Configure Lambda deployment preferences
  - Ingestor: Enable gradual deployment in PROD using FunctionGradualDeploymentType parameter
  - Ingestor: Use AllAtOnce deployment in TEST/DEV
  - Processor: Enable gradual deployment in PROD using FunctionGradualDeploymentType parameter
  - Processor: Use AllAtOnce deployment in TEST/DEV
  - Configure AutoPublishAlias: live for both functions
  - Link deployment alarms to gradual deployment (automatic rollback on alarm)
  - _Requirements: 11.1_

- [x] 20. Configure Lambda environment variables
  - Ingestor: QUEUE_URL, TRACKING_TABLE, PROCESSOR_FUNCTION_ARN, AGGREGATION_WINDOW_SECONDS
  - Processor: QUEUE_URL, TRACKING_TABLE, MAX_BATCH_SIZE, MAX_PATHS_PER_INVALIDATION
  - Both: DEPLOY_ENVIRONMENT, LOG_LEVEL (INFO for PROD, DEBUG for TEST/DEV)
  - Both: AWS_LAMBDA_LOG_LEVEL, AWS_LAMBDA_LOG_FORMAT=json
  - Both: LAMBDA_TIMEOUT_IN_SEC for connection timeout calculations
  - _Requirements: 13.4_

- [x] 21. Create Lambda permissions for S3 invocation
  - Define Lambda Permission for Ingestor to be invoked by S3
  - Set Principal: s3.amazonaws.com
  - Set SourceArn pattern to match Prefix naming convention (with optional S3BucketNameOrgPrefix)
  - Create separate permission for :live alias in PROD (for gradual deployment)
  - _Requirements: 1.1_

- [x] 22. Configure X-Ray tracing
  - Enable X-Ray tracing for both Lambda functions in PROD and TEST
  - Disable X-Ray tracing in DEV
  - Use Condition: IsNotDevelopment
  - Grant Lambda execution roles permission for X-Ray PutTraceSegments
  - _Requirements: 13.3_

- [x] 23. Create CloudFormation Outputs
  - Output Ingestor Lambda ARN (for S3 bucket configuration)
  - Output Processor Lambda ARN
  - Output SQS Queue URL
  - Output DynamoDB Table name
  - Output CloudWatch Log Group links
  - Output Lambda console links
  - _Requirements: 11.1_

- [x] 24. Create requirements.txt for Python dependencies
  - Add boto3 (AWS SDK - already available in Lambda, but include for local testing)
  - Add pytest for unit testing
  - Add pytest-mock for mocking
  - Add hypothesis for property-based testing
  - Add moto for AWS service mocking (optional, for local testing)
  - Pin versions for reproducibility
  - _Requirements: Testing Strategy_

- [x] 25. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 26. Write integration tests for end-to-end flow
  - Test S3 event → Ingestor → SQS → Processor → CloudFront invalidation
  - Test with real AWS services in TEST environment
  - Verify message flow through SQS
  - Verify schedule creation in EventBridge
  - Verify invalidation submission to CloudFront
  - _Requirements: All_

- [x] 27. Write integration tests for IAM permissions
  - Verify Ingestor can write to SQS
  - Verify Processor can read from SQS and delete messages
  - Verify Processor can read S3 bucket tags
  - Verify Processor can list and get CloudFront distributions
  - Verify Processor can create invalidations on tagged distributions
  - Verify tag-based IAM conditions work correctly
  - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 28. Write integration tests for DynamoDB window tracking
  - Verify window creation on first event
  - Verify duplicate schedule prevention
  - Verify window closure after processing
  - Verify TTL cleanup
  - _Requirements: 4.1, 4.2, 4.4_

- [x] 29. Write integration tests for Dead Letter Queue
  - Trigger message processing failures
  - Verify messages move to DLQ after max receives
  - Verify DLQ alarm triggers
  - _Requirements: 3.3_

- [x] 30. Update README.md with new architecture
  - Document the two-Lambda architecture (Ingestor and Processor)
  - Document the aggregation window mechanism
  - Document the path consolidation algorithm
  - Update deployment instructions
  - Document required tags for S3 buckets and CloudFront distributions
  - Document monitoring and troubleshooting
  - _Requirements: All_

- [ ] 31. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
