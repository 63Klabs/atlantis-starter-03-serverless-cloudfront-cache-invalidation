# Requirements Document

## Introduction

This specification addresses a critical path normalization issue in the CloudFront invalidation system. S3 object keys do not include leading slashes (e.g., `app/prod/content/js/file.html`), but the pattern matching logic expects paths with leading slashes (e.g., `/app/prod/content/js/file.html`). This mismatch causes valid S3 events to be incorrectly filtered out, preventing CloudFront invalidations from being triggered.

The fix ensures consistent path handling throughout the system by normalizing S3 object keys to include leading slashes when extracted from events, while maintaining compatibility with CloudFront's path requirements.

## Glossary

- **S3_Object_Key**: The unique identifier for an object in an S3 bucket, representing the full path without a leading slash (e.g., `app/prod/content/js/file.html`)
- **Normalized_Path**: An S3 object key with a leading slash added for internal processing (e.g., `/app/prod/content/js/file.html`)
- **Origin_Path_Pattern**: A pattern template used to match S3 paths, containing optional `{stageId}` placeholder (e.g., `/app/{stageId}`)
- **CloudFront_Invalidation_Path**: The path format required by CloudFront for cache invalidation, which uses leading slashes for non-root paths
- **Event_Parser**: The Lambda function component that extracts metadata from S3 event notifications
- **Pattern_Resolver**: The Lambda function component that matches event paths against bucket-specific patterns
- **Path_Utils**: The shared utility module providing path manipulation and pattern matching functions

## Requirements

### Requirement 1: S3 Object Key Normalization

**User Story:** As a system component, I want S3 object keys to be normalized with leading slashes when extracted from events, so that pattern matching works correctly throughout the system.

#### Acceptance Criteria

1. WHEN an S3 event is parsed, THE Event_Parser SHALL add a leading slash to the object key if not already present
2. WHEN an object key already has a leading slash, THE Event_Parser SHALL preserve it without duplication
3. WHEN an object key is empty or null, THE Event_Parser SHALL handle it gracefully without adding a leading slash
4. THE Event_Parser SHALL normalize object keys before any pattern matching or validation occurs
5. WHEN normalized paths are logged, THE System SHALL clearly indicate they have been normalized for debugging purposes

### Requirement 2: Pattern Matching Compatibility

**User Story:** As a pattern matching component, I want to receive consistently formatted paths with leading slashes, so that I can accurately match events against bucket patterns.

#### Acceptance Criteria

1. WHEN the Pattern_Resolver receives an event path, THE System SHALL ensure it has a leading slash
2. WHEN matching a normalized path against a pattern, THE Path_Utils SHALL correctly identify matches for all valid path formats
3. WHEN a pattern contains `{stageId}`, THE Path_Utils SHALL correctly extract the stage identifier from normalized paths
4. WHEN a pattern is root (`/`), THE Path_Utils SHALL match all normalized paths
5. WHEN pattern matching fails, THE System SHALL log both the event path and pattern for debugging

### Requirement 3: CloudFront Invalidation Path Generation

**User Story:** As a CloudFront invalidation component, I want invalidation paths to be correctly formatted with leading slashes, so that CloudFront cache invalidations work properly.

#### Acceptance Criteria

1. WHEN creating a CloudFront invalidation path from a normalized path, THE System SHALL preserve the leading slash
2. WHEN the origin path is root (`/`), THE System SHALL use `/` as the invalidation path prefix
3. WHEN the origin path is non-root, THE System SHALL ensure the invalidation path starts with the origin path including its leading slash
4. THE System SHALL validate that invalidation paths conform to CloudFront requirements before submission
5. WHEN invalidation paths are generated, THE System SHALL log them for verification

### Requirement 4: Test File Generation Compliance

**User Story:** As a test utility, I want to generate S3 object keys without leading slashes, so that test files accurately simulate real S3 event behavior.

#### Acceptance Criteria

1. WHEN uploading test files to S3, THE Upload_Utility SHALL generate object keys without leading slashes
2. WHEN constructing S3 paths for upload, THE Upload_Utility SHALL strip any leading slashes before calling S3 API
3. WHEN logging upload paths, THE Upload_Utility SHALL display the actual S3 object key format (without leading slash)
4. THE Upload_Utility SHALL validate that generated keys match S3 standard format before upload
5. WHEN test files are uploaded, THE System SHALL verify they trigger events with correctly formatted object keys

### Requirement 5: Backward Compatibility

**User Story:** As a system administrator, I want the path normalization fix to work with existing bucket configurations, so that no manual configuration changes are required.

#### Acceptance Criteria

1. WHEN processing events from existing buckets, THE System SHALL normalize paths without requiring bucket reconfiguration
2. WHEN bucket tags use `@stageId@` notation, THE System SHALL continue to convert them to `{stageId}` internally
3. WHEN existing patterns are evaluated, THE System SHALL work correctly with both old and new event formats
4. THE System SHALL maintain compatibility with all existing origin path pattern formats
5. WHEN the system is deployed, THE System SHALL process both pre-normalization and post-normalization events correctly

### Requirement 6: Edge Case Handling

**User Story:** As a robust system, I want to handle edge cases in path normalization gracefully, so that unexpected input doesn't cause failures.

#### Acceptance Criteria

1. WHEN an object key is exactly `/`, THE System SHALL treat it as a root path
2. WHEN an object key contains multiple consecutive slashes, THE System SHALL normalize them to single slashes
3. WHEN an object key has trailing slashes, THE System SHALL preserve them for pattern matching
4. WHEN an object key contains URL-encoded characters, THE System SHALL handle them correctly
5. IF path normalization encounters an error, THEN THE System SHALL log the error and continue processing other events

### Requirement 7: Logging and Observability

**User Story:** As a system operator, I want detailed logging of path normalization and pattern matching, so that I can diagnose issues quickly.

#### Acceptance Criteria

1. WHEN a path is normalized, THE System SHALL log the original and normalized values at debug level
2. WHEN pattern matching fails, THE System SHALL log the event path, bucket pattern, and failure reason
3. WHEN an event is filtered out, THE System SHALL include the filter reason in structured logs
4. THE System SHALL log path normalization statistics in CloudWatch metrics
5. WHEN debugging is enabled, THE System SHALL provide detailed path transformation traces
