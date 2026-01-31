# Distribution Tag Validation Fix for Missing StageId

## Overview
Fix the distribution tag validation logic in `tag_validator.py` to handle cases where there is no `stageId` in the bucket pattern. Currently, when `stageId` is empty, the validation incorrectly expects an exact match with a trailing hyphen (e.g., `xcme-cdninval-a-`) instead of performing a prefix match.

## Problem Statement
When a bucket pattern does not include `{stageId}`, the `stage_id` variable is set to an empty string. The current validation logic constructs an expected `ApplicationDeploymentId` as `{bucket_app_tag}-{stage_id}`, which results in a trailing hyphen when `stage_id` is empty (e.g., `xcme-cdninval-a-`).

**Current Error Example:**
```
Distribution tag validation failed for E2G4RY69EPFNR7: ApplicationDeploymentId mismatch: 
expected=xcme-cdninval-a-, actual=xcme-cdninval-a-prod
```

**Expected Behavior:**
When there is no `stageId`, the validation should:
1. Construct expected value without trailing hyphen: `xcme-cdninval-a`
2. Perform a prefix match instead of exact match: `xcme-cdninval-a*`
3. Accept any distribution where `ApplicationDeploymentId` starts with the expected prefix

## User Stories

### 1. Distribution Validation Without StageId
**As a** system processing S3 events from buckets without stage-specific paths  
**I want** distribution tag validation to work correctly when there is no stageId  
**So that** invalidations can be processed for distributions serving content from non-staged buckets

**Acceptance Criteria:**
1.1. When `stage_id` is empty string, expected `ApplicationDeploymentId` should not have trailing hyphen  
1.2. When `stage_id` is empty string, validation should perform prefix match instead of exact match  
1.3. Distribution with `ApplicationDeploymentId=xcme-cdninval-a-prod` should match expected `xcme-cdninval-a`  
1.4. Distribution with `ApplicationDeploymentId=xcme-cdninval-a-dev` should match expected `xcme-cdninval-a`  
1.5. Distribution with `ApplicationDeploymentId=xcme-cdninval-a` should match expected `xcme-cdninval-a` (exact match still valid)

### 2. Distribution Validation With StageId (Existing Behavior)
**As a** system processing S3 events from buckets with stage-specific paths  
**I want** distribution tag validation to continue working with exact match when stageId is present  
**So that** existing functionality is not broken

**Acceptance Criteria:**
2.1. When `stage_id` is non-empty (e.g., "prod"), expected `ApplicationDeploymentId` should be `{bucket_app_tag}-{stage_id}`  
2.2. When `stage_id` is non-empty, validation should perform exact match  
2.3. Distribution with `ApplicationDeploymentId=xcme-cdninval-a-prod` should match expected `xcme-cdninval-a-prod`  
2.4. Distribution with `ApplicationDeploymentId=xcme-cdninval-a-dev` should NOT match expected `xcme-cdninval-a-prod`

### 3. AllowInvalidationEvents Tag Validation (Unchanged)
**As a** system validating distribution tags  
**I want** the `AllowInvalidationEvents` tag validation to remain unchanged  
**So that** security controls are maintained

**Acceptance Criteria:**
3.1. `AllowInvalidationEvents` must still equal "true" for validation to pass  
3.2. Both `AllowInvalidationEvents` and `ApplicationDeploymentId` must be valid for overall validation to pass

## Technical Requirements

### Functional Requirements
- **FR-1**: Modify `validate_distribution_tags()` to detect when `stage_id` is empty or None
- **FR-2**: When `stage_id` is empty, construct expected value without trailing hyphen
- **FR-3**: When `stage_id` is empty, use prefix matching (startswith) instead of exact equality
- **FR-4**: When `stage_id` is non-empty, maintain existing exact match behavior
- **FR-5**: Update logging to clearly indicate whether prefix or exact match was used

### Non-Functional Requirements
- **NFR-1**: Changes must be backward compatible with existing stage-based validation
- **NFR-2**: Logging must provide clear diagnostic information for both match types
- **NFR-3**: Code must be maintainable and well-documented

## Constraints
- Must not break existing functionality for buckets with `{stageId}` in pattern
- Must maintain security by still requiring `AllowInvalidationEvents=true`
- Must follow existing code style and logging patterns in the module

## Dependencies
- No new dependencies required
- Existing boto3 and logging infrastructure sufficient

## Success Metrics
- All existing unit tests continue to pass
- New unit tests cover both empty and non-empty `stage_id` scenarios
- Integration tests validate end-to-end behavior with real distribution tags
- No regression in existing stage-based validation functionality
