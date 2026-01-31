# Distribution Tag Validation Fix for Missing StageId - Implementation Tasks

## Overview
This task list implements the fix for distribution tag validation when there is no `stageId` in the bucket pattern. The fix adds conditional logic to use prefix matching instead of exact matching when `stage_id` is empty.

## Tasks

### 1. Code Implementation

- [ ] 1.1 Modify `validate_distribution_tags()` function in `tag_validator.py`
  - Add conditional logic to detect empty/None `stage_id`
  - Implement prefix matching for empty `stage_id` (use `startswith()`)
  - Maintain exact matching for non-empty `stage_id`
  - Update expected value construction to avoid trailing hyphen when `stage_id` is empty
  - Add `match_type` variable to track whether prefix or exact match was used
  - **Validates:** Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, FR-1, FR-2, FR-3, FR-4

- [ ] 1.2 Update logging in `validate_distribution_tags()` function
  - Add `match_type` field to all validation log messages
  - Update success log to indicate match type (prefix or exact)
  - Update failure log to indicate match type
  - Ensure all log messages include expected and actual values
  - **Validates:** Requirements FR-5, NFR-2

- [ ] 1.3 Update function docstring for `validate_distribution_tags()`
  - Document the two validation modes (prefix and exact)
  - Clarify when each mode is used
  - Add examples for both empty and non-empty `stage_id` scenarios
  - Update parameter descriptions
  - **Validates:** Requirements NFR-3

### 2. Unit Testing

- [ ] 2.1 Add unit tests for empty `stage_id` scenarios
  - Test: Empty string `stage_id` with prefix match (valid)
  - Test: Empty string `stage_id` with exact match (valid)
  - Test: Empty string `stage_id` with no prefix match (invalid)
  - Test: None `stage_id` with prefix match (valid)
  - Test: Whitespace-only `stage_id` treated as empty (valid)
  - **Validates:** Requirements 1.1, 1.2, 1.3, 1.4, 1.5

- [ ] 2.2 Add unit tests for non-empty `stage_id` scenarios (regression tests)
  - Test: Non-empty `stage_id` with exact match (valid)
  - Test: Non-empty `stage_id` with different stage (invalid)
  - Test: Non-empty `stage_id` with prefix match but not exact (invalid)
  - **Validates:** Requirements 2.1, 2.2, 2.3, 2.4

- [x] 2.3 Add unit tests for `AllowInvalidationEvents` validation (unchanged behavior)
  - Test: Missing `AllowInvalidationEvents` tag (invalid)
  - Test: `AllowInvalidationEvents` set to "false" (invalid)
  - Test: Valid `ApplicationDeploymentId` but missing `AllowInvalidationEvents` (invalid)
  - **Validates:** Requirements 3.1, 3.2

- [x] 2.4 Add unit tests for edge cases
  - Test: Empty `stage_id` with distribution having no suffix (exact match)
  - Test: Empty `stage_id` with distribution having multiple hyphens in suffix
  - Test: Case sensitivity in prefix matching
  - Test: Distribution with wrong application prefix (invalid)
  - **Validates:** Requirements NFR-1, NFR-2

- [ ] 2.5 Add unit tests for logging verification
  - Test: Verify `match_type` is "prefix" when `stage_id` is empty
  - Test: Verify `match_type` is "exact" when `stage_id` is non-empty
  - Test: Verify log messages include expected and actual values
  - **Validates:** Requirements FR-5

### 3. Integration Testing

- [x] 3.1 Run existing integration tests to verify backward compatibility
  - Ensure all existing tests pass without modification
  - Verify no regression in stage-based validation
  - **Validates:** Requirements NFR-1

- [ ] 3.2 Add integration test for end-to-end flow with empty `stage_id`
  - Test complete flow from S3 event to distribution validation
  - Verify distributions are correctly matched using prefix logic
  - Verify invalidations are created for matching distributions
  - **Validates:** Requirements 1.1, 1.2, 1.3, 1.4, 1.5

### 4. Validation and Documentation

- [ ] 4.1 Run all unit tests and verify they pass
  - Execute: `pytest application-infrastructure/tests/unit/test_tag_validator.py -v`
  - Verify all new tests pass
  - Verify all existing tests still pass
  - **Validates:** Success Metrics

- [ ] 4.2 Run all integration tests and verify they pass
  - Execute: `pytest application-infrastructure/tests/integration/ -v`
  - Verify no regression in existing functionality
  - **Validates:** Success Metrics, NFR-1

- [x] 4.3 Manual testing with sample data
  - Test with bucket pattern without `{stageId}`: verify prefix matching works
  - Test with bucket pattern with `{stageId}`: verify exact matching still works
  - Review CloudWatch logs to verify logging enhancements
  - **Validates:** All requirements

## Task Dependencies

- Task 1.1 must be completed before 1.2 and 1.3
- Task 1.1, 1.2, and 1.3 must be completed before any testing tasks
- Task 2.1, 2.2, 2.3, 2.4, and 2.5 can be done in parallel after 1.x tasks
- Task 3.1 and 3.2 can be done in parallel after 2.x tasks
- Task 4.1, 4.2, and 4.3 should be done sequentially after all implementation and testing tasks

## Success Criteria

- All unit tests pass (existing and new)
- All integration tests pass
- No regression in existing stage-based validation
- Logging clearly indicates match type for both scenarios
- Code is well-documented and maintainable
- Manual testing confirms expected behavior for both empty and non-empty `stage_id`

## Notes

- The fix is fully backward compatible - no changes to existing behavior when `stage_id` is non-empty
- The change only affects the validation logic, not the API signature or return type
- AllowInvalidationEvents validation remains unchanged
- Property-based tests are optional per testing guidelines (focus on unit tests)
