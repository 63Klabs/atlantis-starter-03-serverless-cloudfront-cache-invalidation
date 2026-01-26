# Implementation Plan: Origin Path Pattern

## Overview

This implementation plan breaks down the origin-path-pattern feature into incremental coding tasks. The approach follows a bottom-up strategy: build utilities first, then update Lambda functions, then modify the CloudFormation template, and finally add tests and documentation.

Each task builds on previous work, ensuring no orphaned code. The implementation maintains backward compatibility by using `/{stageId}/public` as the default pattern throughout.

## Tasks

- [ ] 1. Update constants module with new configuration
  - Remove hardcoded ORIGIN_PATH_DEPTH constant
  - Add ORIGIN_PATH_PATTERN with default `/{stageId}/public`
  - Add PUBLIC_PATH_SEGMENT constant with value `public`
  - Add PRODUCTION_STAGE_IDENTIFIERS list
  - Add NON_PRODUCTION_STAGE_IDENTIFIERS list
  - Support ORIGIN_PATH_PATTERN environment variable override
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7, 2.3, 2.4_

- [ ] 1.1 Write unit tests for constants module
  - Test default values for all constants
  - Test environment variable override behavior
  - Test fallback when environment variable is empty
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 2.3, 2.4_

- [ ] 2. Create path utilities module in Lambda layer
  - [ ] 2.1 Implement calculate_path_depth function
    - Calculate depth by counting path segments
    - Handle leading/trailing slashes correctly
    - Return integer count of segments
    - _Requirements: 3.5, 3.6_

  - [ ] 2.2 Write property test for path depth calculation
    - **Property 3: Path Depth Calculation**
    - **Validates: Requirements 3.6, 9.2**
    - Generate random paths and verify depth equals segment count
    - Run with 20 iterations

  - [ ] 2.3 Implement matches_pattern function
    - Check if event path matches origin path pattern
    - Handle {stageId} placeholder replacement
    - Return tuple of (matches: bool, resolved_stage: str or None)
    - _Requirements: 5.1, 5.2_

  - [ ] 2.4 Write unit tests for matches_pattern function
    - Test exact pattern matches with and without {stageId}
    - Test pattern matching with various stage identifiers
    - Test non-matching paths
    - _Requirements: 5.1, 5.2_

  - [ ] 2.5 Implement derive_pattern_from_path function
    - Find PUBLIC_PATH_SEGMENT in event path
    - Extract path up to and including public segment
    - Replace stage identifiers with {stageId} placeholder
    - Return derived pattern string
    - _Requirements: 6.4, 6.5_

  - [ ] 2.6 Write unit tests for derive_pattern_from_path function
    - Test pattern derivation with various path structures
    - Test stage identifier replacement
    - Test paths without public segment
    - _Requirements: 6.4, 6.5_

  - [ ] 2.7 Implement extract_stage_from_path function
    - Extract stage identifier from event path using pattern
    - Handle patterns with and without {stageId}
    - Return stage identifier or empty string
    - _Requirements: 7.1, 7.2, 9.4_

  - [ ] 2.8 Write unit tests for extract_stage_from_path function
    - Test stage extraction with various patterns
    - Test patterns without {stageId} placeholder
    - Test mismatched patterns and paths
    - _Requirements: 7.1, 7.2, 9.4_

- [ ] 3. Update Ingestor function with pattern matching
  - [ ] 3.1 Implement should_process_event function
    - Import constants and path utilities
    - Try exact pattern match with production stages
    - Fall back to public segment detection
    - Filter non-production stages
    - Return boolean indicating whether to queue event
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 3.2 Write property test for production stage filtering
    - **Property 5: Production Stage Filtering with Placeholder**
    - **Validates: Requirements 5.1, 7.1, 7.2**
    - Generate random stage identifiers and paths
    - Verify production stages pass, non-production filtered
    - Run with 20 iterations

  - [ ] 3.3 Write unit tests for should_process_event function
    - Test exact pattern matches with production stages
    - Test exact pattern matches with non-production stages
    - Test public segment fallback with various paths
    - Test filtering of non-matching paths
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 3.4 Integrate should_process_event into Ingestor handler
    - Call should_process_event for each S3 event
    - Queue events that should be processed
    - Log filtered events at debug level
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 4. Checkpoint - Ensure Ingestor tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Update Processor function with pattern resolution
  - [ ] 5.1 Implement resolve_bucket_pattern function
    - Check for invalidator:OriginPathPattern bucket tag
    - Fall back to pattern match with ORIGIN_PATH_PATTERN
    - Derive pattern from public segment if needed
    - Return resolved bucket pattern string
    - _Requirements: 4.1, 4.2, 4.3, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 5.2 Write unit tests for resolve_bucket_pattern function
    - Mock boto3 S3 client for tag retrieval
    - Test bucket tag priority
    - Test fallback to ORIGIN_PATH_PATTERN
    - Test pattern derivation from public segment
    - Test NoSuchTagSet exception handling
    - _Requirements: 4.1, 4.2, 4.3, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 5.3 Implement filter_events_by_pattern function
    - Filter events that match bucket pattern
    - Apply stage filtering for patterns with {stageId}
    - Return filtered event list
    - _Requirements: 6.6, 7.1, 7.2, 7.3, 8.1_

  - [ ] 5.4 Write unit tests for filter_events_by_pattern function
    - Test pattern matching with various event sets
    - Test stage filtering with production and non-production stages
    - Test patterns without {stageId} placeholder
    - Test tag mismatch filtering
    - _Requirements: 6.6, 7.1, 7.2, 7.3, 8.1_

  - [ ] 5.5 Update consolidate_paths function for dynamic depth
    - Calculate depth from bucket pattern using calculate_path_depth
    - Group paths by stage using extract_stage_from_path
    - Consolidate each stage separately
    - Return dictionary mapping stage to consolidated paths
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ] 5.6 Write unit tests for consolidate_paths function
    - Test dynamic depth calculation
    - Test multi-stage separation
    - Test consolidation with various path structures
    - Test empty event list handling
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 8.2_

  - [ ] 5.7 Integrate pattern resolution into Processor handler
    - Call resolve_bucket_pattern with first event path
    - Call filter_events_by_pattern with resolved pattern
    - Skip consolidation if filtered list is empty
    - Pass filtered events and pattern to consolidate_paths
    - Create CloudFront invalidation requests per stage
    - _Requirements: 6.1, 6.2, 8.2, 8.3, 9.4_

- [ ] 6. Checkpoint - Ensure Processor tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Update CloudFormation template with new parameter
  - [ ] 7.1 Add OriginPathPattern parameter
    - Set Type to String
    - Set Default to `/{stageId}/public`
    - Add Description explaining usage and examples
    - Add AllowedPattern regex for validation
    - Add ConstraintDescription with validation rules
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 1.6, 11.1, 11.2, 11.3, 11.4_

  - [ ] 7.2 Write property test for pattern validation
    - **Property 1: Pattern Validation Completeness**
    - **Validates: Requirements 1.3, 1.4, 1.5, 1.6, 11.1, 11.2, 11.3, 11.4**
    - Generate random pattern strings
    - Verify validation accepts/rejects according to rules
    - Run with 20 iterations

  - [ ] 7.3 Write unit tests for CloudFormation template
    - Parse template and verify parameter exists
    - Test specific invalid patterns are rejected
    - Verify default value is correct
    - Verify parameter is in Application Parameters metadata group
    - _Requirements: 1.1, 1.7, 11.1, 11.2, 11.3, 11.4_

  - [ ] 7.4 Add environment variable mapping to Lambda functions
    - Add ORIGIN_PATH_PATTERN to Ingestor function environment
    - Add ORIGIN_PATH_PATTERN to Processor function environment
    - Map to !Ref OriginPathPattern parameter
    - _Requirements: 2.1, 2.2_

  - [ ] 7.5 Write unit tests for environment variable mapping
    - Parse template and verify Ingestor has ORIGIN_PATH_PATTERN
    - Parse template and verify Processor has ORIGIN_PATH_PATTERN
    - Verify both map to OriginPathPattern parameter
    - _Requirements: 2.1, 2.2_

  - [ ] 7.6 Add OriginPathPattern to Application Parameters metadata
    - Add to ParameterGroups in Metadata section
    - Include in Application Parameters group
    - _Requirements: 1.7_

- [ ] 8. Checkpoint - Ensure template validation passes
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Run backward compatibility tests
  - Deploy stack with default parameters
  - Run existing regression test suite
  - Verify identical behavior to previous version
  - Test with various S3 event patterns
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] 10. Update documentation
  - Add Advanced Configuration section for origin path pattern
  - Explain default `/{stageId}/public` pattern
  - Provide examples of valid patterns
  - Explain behavior when pattern is set to `/`
  - Document bucket tag override mechanism
  - Add troubleshooting guidance
  - Recommend multiple stacks for complex environments
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

- [ ] 11. Final checkpoint - Complete implementation
  - Ensure all tests pass
  - Verify CloudFormation template validates
  - Review code for consistency and clarity
  - Ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout implementation
- Property tests are minimal (20 iterations) per project testing guidelines
- Unit tests provide primary coverage for fast feedback
- Implementation maintains backward compatibility with default `/{stageId}/public` pattern
- All code uses Python with type hints and follows existing project patterns
