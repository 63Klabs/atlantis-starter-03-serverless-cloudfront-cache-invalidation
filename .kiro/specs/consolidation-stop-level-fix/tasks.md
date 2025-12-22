# Implementation Plan

- [x] 1. Fix the core stop level logic function
  - Modify `is_consolidation_allowed_at_depth()` function in `path_consolidator.py` to use correct logic
  - Change the comparison from `depth >= stop_level` to `depth <= stop_level`
  - Ensure stop level 0 continues to allow all consolidation (special case)
  - Ensure stop level N > 0 allows consolidation at depth N and shallower
  - _Requirements: 1.1, 1.2, 2.1, 3.1, 3.5_

- [x] 1.1 Write property test for stop level zero behavior
  - **Property 1: Root consolidation for stop level zero**
  - **Validates: Requirements 1.1**

- [x] 1.2 Write property test for stop level zero override
  - **Property 2: Stop level zero override behavior**
  - **Validates: Requirements 1.2**

- [x] 1.3 Write property test for depth-based consolidation allowance
  - **Property 4: Consolidation allowed up to specified depth**
  - **Validates: Requirements 2.1, 3.1**

- [x] 1.4 Write property test for deep depth prevention
  - **Property 5: Consolidation prevented at deep depths**
  - **Validates: Requirements 2.4, 3.5**

- [x] 2. Enhance logging throughout consolidation functions
  - Add detailed logging to `consolidate_index_and_default_files()` for stop level decisions
  - Add detailed logging to `consolidate_by_directory_threshold()` for stop level decisions
  - Add detailed logging to `consolidate_sibling_directories()` for stop level decisions
  - Include depth values and stop level values in all consolidation decision logs
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 2.1 Write property test for stop level prevention logging
  - **Property 7: Stop level prevention logging**
  - **Validates: Requirements 5.1**

- [x] 2.2 Write property test for stop level allowance logging
  - **Property 8: Stop level allowance logging**
  - **Validates: Requirements 5.2**

- [x] 2.3 Write property test for depth calculation logging
  - **Property 9: Depth calculation logging**
  - **Validates: Requirements 5.3**

- [x] 3. Add stop level zero special case handling
  - Modify `consolidate_paths()` main function to handle stop level 0 as immediate root consolidation
  - Add logging for stop level 0 special case behavior
  - Ensure stop level 0 bypasses all other consolidation logic and returns `['/*']`
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 3.1 Write property test for stop level zero logging
  - **Property 3: Stop level zero logging**
  - **Validates: Requirements 1.3**

- [x] 4. Enhance depth calculation accuracy and logging
  - Review and verify `calculate_path_depth()` function works correctly for all path formats
  - Add debug logging to depth calculation function to include calculated depth values
  - Ensure depth calculation is consistent across different root path configurations
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.3_

- [x] 4.1 Write property test for path depth calculation
  - **Property 6: Path depth calculation accuracy**
  - **Validates: Requirements 4.1**

- [x] 5. Update error handling for invalid stop level values
  - Add validation and error handling for invalid ConsolidationStopLevel values
  - Add warning logging when invalid stop level values are encountered
  - Implement fallback to default stop level (1) when invalid values are detected
  - _Requirements: 5.5_

- [x] 5.1 Write property test for invalid stop level logging
  - **Property 10: Invalid stop level logging**
  - **Validates: Requirements 5.5**

- [x] 6. Ensure stop level compliance across all consolidation types
  - Verify index/default file consolidation respects stop level restrictions
  - Verify directory threshold consolidation respects stop level restrictions
  - Verify sibling directory consolidation respects stop level restrictions
  - Ensure stop level takes precedence over other consolidation rules
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6.1 Write property test for index file consolidation compliance
  - **Property 11: Index file consolidation stop level compliance**
  - **Validates: Requirements 6.1**

- [x] 6.2 Write property test for directory threshold consolidation compliance
  - **Property 12: Directory threshold consolidation stop level compliance**
  - **Validates: Requirements 6.2**

- [x] 6.3 Write property test for sibling directory consolidation compliance
  - **Property 13: Sibling directory consolidation stop level compliance**
  - **Validates: Requirements 6.3**

- [x] 6.4 Write property test for consolidation type permission
  - **Property 14: Consolidation type permission at allowed depths**
  - **Validates: Requirements 6.4**

- [x] 6.5 Write property test for stop level precedence
  - **Property 15: Stop level precedence over other rules**
  - **Validates: Requirements 6.5**

- [x] 7. Update existing unit tests for corrected behavior
  - Review and update existing unit tests in `test_path_consolidator.py` to reflect corrected stop level logic
  - Add new unit test cases for stop level edge cases and boundary conditions
  - Ensure backward compatibility tests pass for default stop level 1 behavior
  - Add unit tests for stop level 0 special case behavior
  - _Requirements: 1.4, 2.5_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.