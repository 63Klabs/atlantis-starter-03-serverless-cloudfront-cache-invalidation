# Implementation Plan: S3 Path Normalization Fix

## Overview

This implementation fixes the S3 object key path normalization issue by adding a leading slash to object keys when extracted from S3 events. The fix ensures consistent path handling throughout the CloudFront invalidation system while maintaining compatibility with S3's standard format (no leading slashes) for uploads.

## Tasks

- [x] 1. Implement path normalization in event parser
  - [x] 1.1 Add normalize_s3_path() function to event_parser.py
    - Create function that adds leading slash if not present
    - Collapse multiple consecutive slashes to single slashes
    - Handle edge cases (empty strings, root path, null values)
    - _Requirements: 1.1, 1.2, 6.1, 6.2_
  
  - [x] 1.2 Write unit tests for normalize_s3_path()
    - Test normalization of paths without leading slashes
    - Test idempotence (normalizing already normalized paths)
    - Test edge cases (empty string, root path, multiple slashes)
    - Test trailing slash preservation
    - _Requirements: 1.1, 1.2, 6.1, 6.2, 6.3_
  
  - [x] 1.3 Write property test for normalization idempotence
    - **Property 1: Path Normalization Idempotence**
    - **Validates: Requirements 1.1, 1.2**
    - Use Hypothesis to generate random paths
    - Verify normalize(normalize(x)) == normalize(x)
    - Run with 10-20 iterations for fast execution
  
  - [x] 1.4 Write property test for multiple slash normalization
    - **Property 9: Multiple Slash Normalization**
    - **Validates: Requirements 6.2**
    - Generate paths with various slash patterns
    - Verify consecutive slashes collapse correctly
    - Run with 10-20 iterations for fast execution

- [x] 2. Update extract_event_metadata() to normalize object keys
  - [x] 2.1 Modify extract_event_metadata() to call normalize_s3_path()
    - Extract raw object key from S3 event
    - Call normalize_s3_path() on the raw key
    - Add debug logging for normalization (original vs normalized)
    - Return normalized key in metadata dictionary
    - _Requirements: 1.1, 1.4_
  
  - [x] 2.2 Write unit tests for updated extract_event_metadata()
    - Test extraction with paths that need normalization
    - Test extraction with already normalized paths
    - Test that normalized paths are returned in metadata
    - Test error handling for malformed events
    - _Requirements: 1.1, 2.1_

- [x] 3. Verify pattern matching works with normalized paths
  - [x] 3.1 Review and test pattern_resolver.py with normalized paths
    - Verify filter_events_by_pattern() works with normalized paths
    - Verify resolve_bucket_pattern() handles normalized paths
    - Add logging to show normalized paths in pattern matching
    - _Requirements: 2.1, 2.2_
  
  - [x] 3.2 Write unit tests for pattern matching with normalized paths
    - Test pattern matching with various normalized paths
    - Test stage extraction from normalized paths
    - Test root pattern matching all normalized paths
    - Test bucket tag conversion (@stageId@ to {stageId})
    - _Requirements: 2.2, 2.3, 2.4, 5.2_

- [x] 4. Verify CloudFront invalidation path generation
  - [x] 4.1 Review invalidation path generation logic
    - Verify that normalized paths (with leading slashes) are used correctly
    - Verify root origin path handling
    - Verify non-root origin path handling
    - Add logging for generated invalidation paths
    - _Requirements: 3.1, 3.2, 3.3_
  
  - [x] 4.2 Write unit tests for invalidation path generation
    - Test invalidation paths preserve leading slashes
    - Test root origin path generates correct invalidation paths
    - Test non-root origin paths generate correct invalidation paths
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 5. Fix test file upload utility to generate S3-compliant keys
  - [x] 5.1 Update PathGenerator.generate_upload_paths()
    - Remove leading slashes from base_path before constructing keys
    - Generate keys in format: "stage/public/dir/file.html" (no leading slash)
    - Update path construction logic for all directory depths
    - _Requirements: 4.1_
  
  - [x] 5.2 Update NestedStructureGenerator.generate_nested_structure()
    - Remove leading slashes from base_path before constructing keys
    - Generate nested keys without leading slashes
    - Update all path construction in the nested structure
    - _Requirements: 4.1_
  
  - [x] 5.3 Verify S3Uploader.upload_file() strips leading slashes
    - Confirm existing lstrip('/') behavior is correct
    - Add validation that keys don't start with slashes before upload
    - Update logging to show actual S3 key format
    - _Requirements: 4.2, 4.4_
  
  - [x] 5.4 Write unit tests for updated upload utility
    - Test that generated keys don't have leading slashes
    - Test that upload function strips any leading slashes
    - Test key format validation
    - Test both legacy and nested structure key generation
    - _Requirements: 4.1, 4.2, 4.4_

- [x] 6. Integration testing and verification
  - [x] 6.1 Run full test suite
    - Execute all unit tests
    - Execute property tests (with minimal iterations)
    - Verify test suite completes in under 30 seconds
    - Fix any failing tests
  
  - [x] 6.2 Manual verification with test files
    - Upload test files using updated utility
    - Verify S3 object keys don't have leading slashes
    - Verify S3 events trigger with correct object keys
    - Verify events are normalized and matched correctly
    - Verify CloudFront invalidations are created with correct paths

- [x] 7. Update logging and observability
  - [x] 7.1 Add structured logging for path normalization
    - Log original and normalized paths at debug level
    - Log pattern matching results with normalized paths
    - Include filter reasons in structured logs
    - _Requirements: 7.1, 7.2, 7.3_
  
  - [x] 7.2 Verify CloudWatch metrics capture normalization events
    - Ensure existing metrics include normalized path processing
    - Add any missing metrics for path normalization
    - _Requirements: 7.4_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Property tests use minimal iterations (10-20) to maintain fast test execution
- Focus on comprehensive unit tests rather than extensive property-based testing
- Test suite should complete in under 30 seconds per repository guidelines
