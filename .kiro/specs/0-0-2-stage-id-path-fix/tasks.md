# Implementation Plan: Stage ID Extraction Fix

## Overview

This plan implements a critical bug fix for the processor Lambda function's stage extraction logic. The fix replaces hardcoded logic that always extracts the first path segment with a call to the existing `extract_stage_from_path()` utility function that correctly handles `{stageId}` placeholders at any position in the pattern.

The implementation is straightforward: add an import statement and replace 10 lines of buggy code with a single function call. The bulk of the work involves adding comprehensive tests to verify the fix and prevent regressions.

## Tasks

- [x] 1. Fix stage extraction logic in handler.py
  - Add import for `extract_stage_from_path` from common.path_utils
  - Replace hardcoded stage extraction logic (lines 502-512) with call to `extract_stage_from_path(object_key, bucket_pattern)`
  - Verify the fix compiles without errors
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 2. Add unit tests for stage extraction in handler
  - [x] 2.1 Create test class for stage extraction scenarios
    - Test stage at first position: `/{stageId}/public` with `/prod/public/file.html` → "prod"
    - Test stage at second position: `/app/{stageId}/web` with `/app/prod/web/file.html` → "prod"
    - Test stage at third position: `/app/web/{stageId}/public` with `/app/web/prod/public/file.html` → "prod"
    - Test no stage placeholder: `/public` with `/public/file.html` → ""
    - Test multiple segments after stage: `/{stageId}/public` with `/dev/public/assets/file.html` → "dev"
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 2.2 Test message grouping by extracted stage
    - Create messages with different stages and verify correct grouping
    - Test empty stage handling (messages with no stage placeholder)
    - Verify messages with same stage are grouped together
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Add integration tests for end-to-end processing
  - [x] 3.1 Test distribution matching with correct stage
    - Mock S3 events with pattern `/app/web/{stageId}/web`
    - Verify distribution matching receives correct stage identifier
    - Verify tag validation receives correct stage identifier
    - _Requirements: 3.4_

  - [x] 3.2 Test processing with various pattern positions
    - Test pattern with stage at first position
    - Test pattern with stage at middle position
    - Test pattern with stage at last position
    - Test pattern without stage placeholder
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 4. Run regression tests
  - Execute existing test suite to ensure no regressions
  - Verify all existing tests pass
  - Check that logging, error handling, and message deletion still work correctly
  - _Requirements: 3.5_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- The fix is minimal: one import and one line of code replacement
- The existing `extract_stage_from_path()` function is already well-tested in `test_path_utils.py`
- Focus testing on integration points where the handler uses the extracted stage
- Per project guidelines, use fast-running unit tests rather than property-based tests
- All tests should complete in under 30 seconds total
