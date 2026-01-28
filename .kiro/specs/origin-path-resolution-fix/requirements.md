# Requirements Document

## Introduction

This specification addresses a defect in the CloudFront invalidation system where the bucket's `invalidator:OriginPathPattern` tag is not being used to determine the origin path when searching for CloudFront distributions. Currently, the system searches for distributions using the origin path from the S3 event (typically `/`) instead of the resolved origin path from the bucket's tag pattern (e.g., `/app/prod`), causing distribution lookup failures.

## Glossary

- **Processor**: The Lambda function that processes S3 events and triggers CloudFront invalidations
- **Origin_Path**: The path prefix configured in a CloudFront distribution's origin settings
- **Origin_Path_Pattern**: A template pattern stored in the bucket tag that may contain placeholders like `{stageId}`
- **Stage_Id**: An environment identifier (e.g., `prod`, `staging`, `dev`) extracted from the S3 object key
- **Distribution_Finder**: The module responsible for querying CloudFront distributions by bucket and origin path
- **Pattern_Resolver**: The module responsible for resolving bucket tag patterns and replacing placeholders

## Requirements

### Requirement 1: Resolve Origin Path Before Distribution Search

**User Story:** As a system operator, I want the Processor to use the bucket's origin path pattern when searching for CloudFront distributions, so that distributions with non-root origin paths are correctly identified.

#### Acceptance Criteria

1. WHEN the Processor receives S3 events for a bucket with an `invalidator:OriginPathPattern` tag, THE Processor SHALL resolve the pattern using the Pattern_Resolver before searching for distributions
2. WHEN a bucket has an `invalidator:OriginPathPattern` tag, THE Processor SHALL use the bucket's pattern instead of the default ORIGIN_PATH_PATTERN environment variable, regardless of whether the bucket pattern is root or non-root
3. WHEN the resolved pattern contains a `{stageId}` placeholder, THE Processor SHALL extract the Stage_Id from the S3 event and replace the placeholder with the actual stage value
4. WHEN calling the Distribution_Finder, THE Processor SHALL use the resolved Origin_Path instead of the event's origin path
5. WHEN a bucket does not have an `invalidator:OriginPathPattern` tag, THE Processor SHALL use the default ORIGIN_PATH_PATTERN environment variable for distribution search
6. WHEN multiple events have different Stage_Id values for the same bucket, THE Processor SHALL resolve separate origin paths for each stage

### Requirement 2: Maintain Event Grouping Logic

**User Story:** As a system operator, I want events to be grouped correctly by bucket and resolved origin path, so that invalidations are batched efficiently.

#### Acceptance Criteria

1. WHEN grouping S3 events, THE Processor SHALL group events by the tuple `(bucket_name, resolved_origin_path)` instead of `(bucket_name, event_origin_path)`
2. WHEN events for the same bucket have different Stage_Id values, THE Processor SHALL create separate groups for each unique resolved origin path
3. WHEN events for the same bucket and stage are received, THE Processor SHALL group them together into a single batch

### Requirement 3: Preserve Existing Pattern Resolution Logic

**User Story:** As a system maintainer, I want the existing Pattern_Resolver functionality to remain unchanged, so that pattern normalization and validation continue to work correctly.

#### Acceptance Criteria

1. THE Processor SHALL continue to use the Pattern_Resolver's `resolve_bucket_pattern()` function without modification
2. THE Processor SHALL continue to normalize patterns by ensuring they start with `/` and do not end with `/`, except when the pattern is exactly `/` (root)
3. WHEN a pattern contains `@stageId@` syntax, THE Pattern_Resolver SHALL convert it to `{stageId}` format
4. THE Pattern_Resolver SHALL continue to validate that patterns do not contain invalid characters or multiple consecutive slashes

### Requirement 4: Handle Edge Cases Gracefully

**User Story:** As a system operator, I want the Processor to handle edge cases without failing, so that the invalidation system remains robust.

#### Acceptance Criteria

1. WHEN a bucket has an `invalidator:OriginPathPattern` tag without a `{stageId}` placeholder, THE Processor SHALL use the pattern as-is for distribution search
2. WHEN a bucket's pattern contains a `{stageId}` placeholder but the Stage_Id cannot be extracted from events, THE Processor SHALL log a warning and skip those events
3. WHEN the resolved origin path is empty or invalid, THE Processor SHALL log an error and skip those events
4. WHEN the Pattern_Resolver raises an exception, THE Processor SHALL log the error and continue processing other event groups
5. WHEN multiple placeholders exist in a pattern, THE Processor SHALL replace all occurrences of `{stageId}` with the extracted stage value

### Requirement 5: Maintain Backward Compatibility

**User Story:** As a system operator, I want existing buckets without origin path patterns to continue working, so that the fix does not break current functionality.

#### Acceptance Criteria

1. WHEN a bucket does not have an `invalidator:OriginPathPattern` tag, THE Processor SHALL search for distributions using the default ORIGIN_PATH_PATTERN environment variable
2. WHEN a bucket has an `invalidator:OriginPathPattern` tag set to `/` (root), THE Processor SHALL convert it to an empty string `""` when searching for CloudFront distributions
3. WHEN a bucket has an `invalidator:OriginPathPattern` tag with a non-root path, THE Processor SHALL use the pattern as-is for distribution search
4. THE Processor SHALL maintain the existing behavior for all buckets that do not have the `invalidator:OriginPathPattern` tag
5. THE Processor SHALL continue to support all existing tag formats and patterns

### Requirement 6: Log Origin Path Resolution

**User Story:** As a system operator, I want detailed logging of origin path resolution, so that I can troubleshoot distribution lookup issues.

#### Acceptance Criteria

1. WHEN resolving a bucket's origin path pattern, THE Processor SHALL log the original pattern and the resolved origin path
2. WHEN extracting Stage_Id from events, THE Processor SHALL log the extracted stage value
3. WHEN searching for distributions, THE Processor SHALL log the bucket name and resolved origin path being used
4. WHEN origin path resolution fails, THE Processor SHALL log the error with sufficient context for debugging
