# Implementation Plan

- [x] 1. Add sibling_threshold parameter to consolidate_paths function
  - Update function signature to accept `sibling_threshold` parameter with default None
  - Pass sibling_threshold parameter to consolidate_sibling_directories function
  - Ensure backward compatibility when parameter is not provided
  - Update function documentation to describe the new parameter
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 1.1 Update consolidate_paths function signature
  - Add `sibling_threshold: int = None` parameter to function signature
  - Update docstring to document the new parameter
  - Ensure parameter is passed through to consolidation logic
  - _Requirements: 1.1, 1.3_

- [x] 1.2 Update consolidate_sibling_directories function signature
  - Add `sibling_threshold: int = None` parameter to function signature
  - Use provided threshold instead of global constant when available
  - Fall back to global constant when parameter is None
  - Update function documentation
  - _Requirements: 3.1, 3.2, 3.3, 3.5_

- [x] 1.3 Update consolidate_paths_recursive function
  - Pass sibling_threshold parameter through to consolidate_sibling_directories
  - Ensure parameter propagation through recursive calls
  - Maintain backward compatibility
  - _Requirements: 1.3, 3.5_

- [x] 1.4 Write property test for sibling threshold parameter
  - **Property 1: Sibling threshold parameter usage**
  - **Validates: Requirements 1.1, 1.2**

- [x] 2. Update processor handler to pass bucket-specific sibling threshold
  - Modify consolidate_paths call in handler.py to include sibling_directory_threshold
  - Extract sibling_directory_threshold from bucket_config
  - Ensure proper parameter passing from bucket configuration
  - Test with bucket-specific configuration
  - _Requirements: 1.4, 2.1, 2.4_

- [x] 2.1 Update handler.py consolidate_paths call
  - Add `sibling_threshold=bucket_config['sibling_directory_threshold']` parameter
  - Verify bucket_config contains sibling_directory_threshold key
  - Test with various bucket configurations
  - _Requirements: 1.4, 2.4_

- [x] 2.2 Write property test for bucket-specific threshold usage
  - **Property 2: Bucket-specific sibling threshold usage**
  - **Validates: Requirements 2.1, 2.4**

- [x] 3. Test and verify the fix with user's specific scenario
  - Create test case with exact paths from user's example
  - Configure bucket tags with SiblingDirectoryConsolidationThreshold=2
  - Verify output is `/prod/public/*` instead of separate directory wildcards
  - Test with ConsolidationStopLevel=1 to ensure stop level logic works
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 3.1 Create test for user's specific scenario
  - Test with paths: `/prod/public/m/*`, `/prod/public/k/*`, `/prod/public/w/*`, `/prod/public/x/*`
  - Configure SiblingDirectoryConsolidationThreshold=2 and ConsolidationStopLevel=1
  - Verify consolidation to `/prod/public/*`
  - _Requirements: 2.3_

- [x] 3.2 Test threshold boundary conditions
  - Test with sibling count exactly at threshold
  - Test with sibling count just above and below threshold
  - Verify correct consolidation behavior
  - _Requirements: 2.1, 2.2_

- [x] 3.3 Write property test for threshold boundary conditions
  - **Property 3: Sibling threshold boundary conditions**
  - **Validates: Requirements 2.1, 2.2**

- [x] 4. Verify backward compatibility and existing functionality
  - Run existing test suite to ensure no regressions
  - Test default behavior when no sibling_threshold parameter is provided
  - Verify global constant is still used as fallback
  - Test with various stop level configurations
  - _Requirements: 1.3, 3.3, 3.5_

- [x] 4.1 Run existing unit tests
  - Ensure all existing path consolidation tests pass
  - Verify no breaking changes to existing functionality
  - Test default parameter behavior
  - _Requirements: 1.3, 3.5_

- [x] 4.2 Test backward compatibility scenarios
  - Test consolidate_paths calls without sibling_threshold parameter
  - Verify global constant fallback behavior
  - Test with existing bucket configurations
  - _Requirements: 1.3, 3.3_

- [x] 4.3 Write property test for backward compatibility
  - **Property 4: Backward compatibility with missing parameter**
  - **Validates: Requirements 1.3, 3.3**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Update documentation and add comprehensive tests
  - Update function documentation for new parameter
  - Add unit tests for various threshold configurations
  - Test integration with bucket tag configuration
  - Document the fix and parameter usage
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 6.1 Update function documentation
  - Update docstrings for consolidate_paths and consolidate_sibling_directories
  - Add examples of sibling_threshold parameter usage
  - Document parameter behavior and fallback logic
  - _Requirements: 4.5_

- [x] 6.2 Add comprehensive unit tests
  - Test various sibling threshold values
  - Test interaction with stop level constraints
  - Test edge cases and error conditions
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 6.3 Write property test for comprehensive threshold testing
  - **Property 5: Comprehensive sibling threshold behavior**
  - **Validates: Requirements 4.1, 4.2, 4.3**

- [x] 7. Final validation and integration testing
  - Test complete end-to-end flow with bucket tags
  - Verify fix resolves the original user issue
  - Test with various bucket configurations
  - Validate performance and error handling
  - _Requirements: All requirements_

- [x] 7.1 End-to-end integration testing
  - Test with realistic bucket tag configurations
  - Verify complete consolidation flow works correctly
  - Test with multiple buckets and different thresholds
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 7.2 Performance and error handling validation
  - Verify no performance regression with new parameter
  - Test error handling with invalid threshold values
  - Validate memory usage and processing time
  - _Requirements: 4.4, 4.5_

- [x] 8. Final Checkpoint - Make sure all tests are passing
  - Ensure all tests pass, ask the user if questions arise.