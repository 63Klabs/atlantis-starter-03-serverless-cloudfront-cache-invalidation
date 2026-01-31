# Requirements Document

## Introduction

This document specifies the requirements for fixing a critical bug in the CloudFront invalidation processor function. The processor currently uses hardcoded logic to extract the stage identifier from S3 object paths, always taking the first path segment regardless of where `{stageId}` appears in the origin path pattern. This causes incorrect stage identification, leading to distribution matching failures, tag validation failures, and invalidation failures.

The fix involves replacing the hardcoded extraction logic with a call to the existing `extract_stage_from_path()` utility function that correctly handles `{stageId}` placeholders at any position in the pattern.

## Glossary

- **Processor_Function**: The Lambda function that processes queued S3 events and submits CloudFront invalidations
- **Stage_Identifier**: A string value (e.g., "prod", "dev", "staging") that identifies the deployment stage
- **Origin_Path_Pattern**: A path template that may contain `{stageId}` placeholder (e.g., "/{stageId}/public", "/app/web/{stageId}/web")
- **Object_Key**: The full S3 object path from an event (e.g., "/app/web/prod/public/file.html")
- **Path_Utils_Module**: The common utility module containing path manipulation functions
- **Distribution_Matching**: The process of finding CloudFront distributions that match a bucket and origin path
- **Tag_Validation**: The process of verifying that distribution tags match expected values based on stage

## Requirements

### Requirement 1: Correct Stage Extraction

**User Story:** As a system operator, I want the processor to correctly extract stage identifiers from S3 object paths regardless of the `{stageId}` position in the pattern, so that distributions are matched and validated correctly.

#### Acceptance Criteria

1. WHEN the origin path pattern is "/{stageId}/public" AND the object key is "/prod/public/file.html", THE Processor_Function SHALL extract "prod" as the stage identifier
2. WHEN the origin path pattern is "/app/web/{stageId}/web" AND the object key is "/app/web/prod/public/file.html", THE Processor_Function SHALL extract "prod" as the stage identifier
3. WHEN the origin path pattern is "/prefix/{stageId}/suffix" AND the object key is "/prefix/staging/suffix/file.html", THE Processor_Function SHALL extract "staging" as the stage identifier
4. WHEN the origin path pattern does not contain "{stageId}" AND the object key is "/public/file.html", THE Processor_Function SHALL extract an empty string as the stage identifier
5. WHEN the origin path pattern is "/{stageId}/public" AND the object key is "/dev/public/assets/file.html", THE Processor_Function SHALL extract "dev" as the stage identifier

### Requirement 2: Use Existing Utility Function

**User Story:** As a developer, I want the processor to use the existing `extract_stage_from_path()` utility function, so that stage extraction logic is centralized and maintainable.

#### Acceptance Criteria

1. THE Processor_Function SHALL call the `extract_stage_from_path()` function from the Path_Utils_Module
2. THE Processor_Function SHALL pass the object key and bucket pattern as arguments to `extract_stage_from_path()`
3. THE Processor_Function SHALL NOT implement custom stage extraction logic
4. THE Processor_Function SHALL import `extract_stage_from_path` from the common layer

### Requirement 3: Preserve Existing Behavior

**User Story:** As a system operator, I want the fix to preserve all existing functionality except the stage extraction logic, so that no regressions are introduced.

#### Acceptance Criteria

1. WHEN processing messages grouped by bucket, THE Processor_Function SHALL continue to group filtered messages by stage
2. WHEN the extracted stage identifier is empty, THE Processor_Function SHALL use an empty string as the stage group key
3. WHEN multiple messages have the same stage identifier, THE Processor_Function SHALL group them together for processing
4. WHEN distribution matching and tag validation occur, THE Processor_Function SHALL use the correctly extracted stage identifier
5. THE Processor_Function SHALL maintain all existing logging, error handling, and message deletion behavior

### Requirement 4: Maintain Test Coverage

**User Story:** As a developer, I want comprehensive test coverage for stage extraction, so that the fix is verified and future regressions are prevented.

#### Acceptance Criteria

1. THE test suite SHALL include unit tests for stage extraction with `{stageId}` at various positions in the pattern
2. THE test suite SHALL include unit tests for stage extraction without `{stageId}` in the pattern
3. THE test suite SHALL include integration tests that verify end-to-end processing with correct stage extraction
4. THE test suite SHALL verify that distribution matching uses the correctly extracted stage
5. THE test suite SHALL verify that tag validation uses the correctly extracted stage
