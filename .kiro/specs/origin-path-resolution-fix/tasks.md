# Implementation Plan: Origin Path Resolution Fix

## Overview

This plan implements a surgical fix to the CloudFront invalidation processor to use the resolved bucket origin path pattern (with stage substitution) when searching for distributions, instead of using the event's origin path.

## Tasks

- [x] 1. Add origin path resolution logic to handler.py
  - Insert new code after the existing `filter_events_by_pattern()` call
  - Extract stage ID from first filtered event
  - Construct resolved origin path by replacing `{stageId}` placeholder with actual stage
  - Convert root path `/` to empty string `""` for CloudFront compatibility
  - Add comprehensive logging for the resolution process
  - Handle edge case where pattern has `{stageId}` but no stage is found
  - _Requirements: 1.1, 1.2, 1.3, 4.2, 5.2, 6.1_

- [x] 2. Update find_matching_distributions() call
  - Change the call from `find_matching_distributions(bucket_name, origin_path)` to `find_matching_distributions(bucket_name, resolved_origin_path)`
  - Ensure the resolved_origin_path variable is used instead of the origin_path from event grouping
  - _Requirements: 1.4_

- [x] 3. Write unit tests for origin path resolution
  - [x] 3.1 Test bucket with stage-specific pattern
    - Mock bucket with tag `invalidator:OriginPathPattern=/app/@stageId@`
    - Create events with `stageId='prod'`
    - Verify `find_matching_distributions()` called with `/app/prod`
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [x] 3.2 Test bucket with root pattern
    - Mock bucket with tag `invalidator:OriginPathPattern=/`
    - Verify `find_matching_distributions()` called with empty string `""`
    - _Requirements: 5.2_
  
  - [x] 3.3 Test bucket without pattern tag
    - Mock bucket without `invalidator:OriginPathPattern` tag
    - Verify `find_matching_distributions()` called with default ORIGIN_PATH_PATTERN
    - _Requirements: 1.5, 5.1_
  
  - [x] 3.4 Test pattern without stage placeholder
    - Mock bucket with tag `invalidator:OriginPathPattern=/public`
    - Verify `find_matching_distributions()` called with `/public`
    - _Requirements: 4.1_
  
  - [x] 3.5 Test missing stageId with stage placeholder
    - Mock bucket with pattern containing `{stageId}`
    - Create events missing `stageId` field
    - Verify warning logged and events skipped without crash
    - _Requirements: 4.2_
  
  - [x] 3.6 Test multiple placeholders in pattern
    - Mock bucket with pattern containing multiple `{stageId}` occurrences
    - Verify all placeholders are replaced with the same stage value
    - _Requirements: 4.5_

- [x] 4. Write integration test for complete flow
  - Mock S3 bucket with `invalidator:OriginPathPattern=/app/@stageId@` tag
  - Mock CloudFront distribution with origin path `/app/prod`
  - Create SQS messages with `stageId='prod'`
  - Execute handler and verify correct distribution is found
  - Verify invalidation is submitted to the correct distribution
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 5. Write backward compatibility test
  - Mock bucket without `invalidator:OriginPathPattern` tag
  - Mock CloudFront distribution with root origin path (empty string)
  - Create SQS messages
  - Execute handler and verify existing behavior is maintained
  - _Requirements: 5.1, 5.3, 5.4_

- [x] 6. Checkpoint - Ensure all tests pass
  - Run all unit tests and integration tests
  - Verify no regressions in existing functionality
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- This is a minimal, surgical fix that only changes the origin path value passed to `find_matching_distributions()`
- Pattern resolution and event filtering logic remain unchanged (they are working correctly)
- All tests use pytest framework per repository standards
- Tests should complete quickly (< 5 seconds total for unit tests)
- Integration tests may take longer but should still be fast (< 10 seconds)
